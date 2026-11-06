#include "cim/Codegen/CIMPasses.h"

#include "cim/Codegen/CIMMVMUtils.h"
#include "cim/IR/CIMOps.h"
#include "iree/compiler/Codegen/Utils/Utils.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/Dialect/Bufferization/Transforms/BufferViewFlowAnalysis.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/Dialect/MemRef/Utils/MemRefUtils.h"
#include "mlir/Dialect/Utils/StaticValueUtils.h"
#include "mlir/Interfaces/SideEffectInterfaces.h"
#include "mlir/Pass/Pass.h"
#include "llvm/ADT/BitVector.h"
#include "llvm/Support/CheckedArithmetic.h"

#include <limits>
#include <optional>

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMMATERIALIZESRAMPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

enum class StorageOrigin { Boundary, Embedded };

struct Access {
  bool reads = false;
  bool writes = false;
};

struct Storage {
  Value source;
  StorageOrigin origin;
  Access access = {};
};

static bool hasArrayMemorySpace(MemRefType type) {
  auto space = dyn_cast_or_null<MemorySpaceAttr>(type.getMemorySpace());
  return space && space.getValue() == MemorySpace::Array;
}

static Value getBoundaryStorageView(Value root) {
  Value value = root;
  while (value.hasOneUse()) {
    Operation *user = value.use_begin()->getOwner();
    if (isa<memref::CastOp>(user)) {
      value = user->getResult(0);
      continue;
    }
    if (auto subview = dyn_cast<memref::SubViewOp>(user))
      return subview.getResult();
    break;
  }
  return root;
}

static Access getSRAMAccess(const BufferViewFlowAnalysis::ValueSetT &aliases) {
  Access access;
  for (Value alias : aliases) {
    for (OpOperand &use : alias.getUses()) {
      Operation *user = use.getOwner();
      if (auto load = dyn_cast<ArrayLoadOp>(user);
          load && load.getSrc() == alias)
        continue;
      access.reads |= hasEffect<MemoryEffects::Read>(user, alias);
      access.writes |= hasEffect<MemoryEffects::Write>(user, alias);
    }
  }
  return access;
}

// Prove reads and export covered by full writes to contiguous, constant-offset
// views of the compact staging allocation. A cast may relax its type's offset,
// so recover the address from the same view chain used by serialization.
static bool needsBoundaryImport(func::FuncOp func, Value storage,
                                bool exportToBoundary) {
  auto storageType = cast<MemRefType>(storage.getType());
  int64_t elements = storageType.getNumElements();
  if (elements > std::numeric_limits<unsigned>::max())
    return true;
  llvm::BitVector initialized(static_cast<unsigned>(elements));
  BufferViewFlowAnalysis views(func);
  auto aliases = views.resolve(storage);
  auto interval =
      [&](Value value) -> std::optional<std::pair<unsigned, unsigned>> {
    int64_t byteOffset = 0;
    auto root = resolveBufferBase(value, [&](OpFoldResult term, int64_t scale) {
      auto constant = getConstantIntValue(term);
      auto total = constant ? llvm::checkedMulAdd(*constant, scale, byteOffset)
                            : std::nullopt;
      if (!total)
        return failure();
      byteOffset = *total;
      return success();
    });
    auto type = cast<MemRefType>(value.getType());
    int64_t elementBytes = storageType.getElementTypeBitWidth() / 8;
    if (failed(root) || *root != storage || !elementBytes || byteOffset < 0 ||
        byteOffset % elementBytes ||
        type.getElementType() != storageType.getElementType() ||
        !memref::isStaticShapeAndContiguousRowMajor(type))
      return std::nullopt;
    int64_t offset = byteOffset / elementBytes;
    if (offset > elements || type.getNumElements() > elements - offset)
      return std::nullopt;
    return std::pair<unsigned, unsigned>{
        static_cast<unsigned>(offset),
        static_cast<unsigned>(offset + type.getNumElements())};
  };
  for (Operation &op : func.getBody().front()) {
    auto effects = getEffectsRecursively(&op);
    if (!effects)
      return true;
    for (const auto &effect : *effects) {
      if (!isa<MemoryEffects::Read>(effect.getEffect()) ||
          !effect.getResource()->isAddressable())
        continue;
      if (!effect.getValue())
        return true;
      if (!aliases.contains(effect.getValue()))
        continue;
      auto range = interval(effect.getValue());
      if (!range ||
          initialized.find_first_unset_in(range->first, range->second) != -1)
        return true;
    }
    // Writes in a nested region need not execute. Reads are checked first so
    // an in-place operation cannot initialize its own input retroactively.
    if (op.getNumRegions())
      continue;
    for (const auto &effect : *effects) {
      if (isa<MemoryEffects::Write>(effect.getEffect()) &&
          effect.getEffectOnFullRegion() && aliases.contains(effect.getValue()))
        if (auto range = interval(effect.getValue()))
          initialized.set(range->first, range->second);
    }
  }
  // Export reads the whole staged view, including portions with no IR reads.
  return exportToBoundary && !initialized.all();
}

static LogicalResult materializeFunction(func::FuncOp func) {
  bool hasCompute = false;
  func.walk([&](Operation *op) { hasCompute |= isa<MvmOp, EltOp>(op); });
  if (!hasCompute)
    return success();

  BufferViewFlowAnalysis views(func);

  SmallVector<Storage> storages;
  func.walk([&](IREE::HAL::InterfaceBindingSubspanOp op) {
    Value source = getBoundaryStorageView(op.getResult());
    auto type = dyn_cast<MemRefType>(source.getType());
    if (type && type.hasStaticShape())
      storages.push_back({source, StorageOrigin::Boundary});
  });
  func.walk([&](memref::GetGlobalOp op) {
    if (!hasArrayMemorySpace(op.getType()))
      storages.push_back({op.getResult(), StorageOrigin::Embedded});
  });
  // Freeze access facts before inserting copies or redirecting any uses.
  for (Storage &storage : storages)
    storage.access = getSRAMAccess(views.resolve(storage.source));

  IRRewriter rewriter(func.getContext());
  for (const Storage &storage : storages) {
    Value source = storage.source;
    const Access &access = storage.access;
    if (!access.reads && !access.writes)
      continue;
    bool exportToBoundary =
        storage.origin == StorageOrigin::Boundary && access.writes;

    auto type = cast<MemRefType>(source.getType());
    auto sramType = MemRefType::get(type.getShape(), type.getElementType());
    if (failed(canReplaceMemrefUsesAndPropagateType(source, sramType)))
      return source.getDefiningOp()->emitError(
          "cannot propagate CIM SRAM type through buffer views");

    rewriter.setInsertionPointAfter(source.getDefiningOp());
    Value sram = memref::AllocOp::create(rewriter, source.getLoc(), sramType);
    replaceMemrefUsesAndPropagateType(rewriter, source.getLoc(), source, sram);

    bool import = storage.origin == StorageOrigin::Embedded ||
                  needsBoundaryImport(func, sram, exportToBoundary);
    rewriter.setInsertionPointAfter(sram.getDefiningOp());
    if (import)
      memref::CopyOp::create(rewriter, source.getLoc(), source, sram);
    if (exportToBoundary) {
      Operation *terminator = func.getBody().front().getTerminator();
      OpBuilder exportBuilder(terminator);
      memref::CopyOp::create(exportBuilder, terminator->getLoc(), sram, source);
    }
  }
  return success();
}

static LogicalResult
materializeVariant(IREE::HAL::ExecutableVariantOp variant) {
  variant.getInnerModule().walk([](memref::AssumeAlignmentOp op) {
    op.replaceAllUsesWith(op.getMemref());
    op.erase();
  });
  for (auto func : variant.getInnerModule().getOps<func::FuncOp>())
    if (failed(materializeFunction(func)))
      return failure();

  return success();
}

struct CIMMaterializeSRAMPass final
    : impl::CIMMaterializeSRAMPassBase<CIMMaterializeSRAMPass> {
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<memref::MemRefDialect, CIMDialect>();
  }

  void runOnOperation() override {
    for (auto variant : cimVariants(getOperation()))
      if (failed(materializeVariant(variant)))
        return signalPassFailure();
  }
};

} // namespace
} // namespace mlir::iree_compiler::IREE::CIM
