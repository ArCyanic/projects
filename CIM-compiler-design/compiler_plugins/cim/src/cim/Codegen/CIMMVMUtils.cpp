#include "cim/Codegen/CIMMVMUtils.h"

#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Bufferization/IR/Bufferization.h"
#include "mlir/Dialect/Linalg/IR/Linalg.h"
#include "mlir/Dialect/Linalg/IR/LinalgInterfaces.h"
#include "mlir/Dialect/MemRef/Utils/MemRefUtils.h"
#include "mlir/Dialect/Utils/StaticValueUtils.h"
#include "mlir/IR/BuiltinAttributes.h"
#include "mlir/Interfaces/ViewLikeInterface.h"
#include "llvm/Support/CheckedArithmetic.h"

namespace mlir::iree_compiler::IREE::CIM {

bool isSignedContraction(linalg::LinalgOp op) {
  if (auto cast = op->getAttrOfType<linalg::TypeFnAttr>("cast");
      cast && cast.getValue() == linalg::TypeFn::cast_unsigned)
    return false;
  return linalg::isaContractionOpInterface(op) &&
         linalg::detail::isContractionBody(
             *op.getBlock(),
             [](Operation *multiply, Operation *add) {
               return isa<arith::MulIOp>(multiply) && isa<arith::AddIOp>(add);
             }) &&
         llvm::all_of(op.getBlock()->getOperations(), [](Operation &scalar) {
           return isa<arith::ExtSIOp, arith::MulIOp, arith::AddIOp,
                      linalg::YieldOp>(scalar);
         });
}

bool mayAlias(Value lhs, Value rhs, AliasAnalysis &analysis) {
  Value a = memref::skipViewLikeOps(cast<MemrefValue>(lhs));
  Value b = memref::skipViewLikeOps(cast<MemrefValue>(rhs));
  if (a == b)
    return true;
  auto aBinding = a.getDefiningOp<IREE::HAL::InterfaceBindingSubspanOp>();
  auto bBinding = b.getDefiningOp<IREE::HAL::InterfaceBindingSubspanOp>();
  if (aBinding && bBinding && aBinding.getLayout() == bBinding.getLayout())
    return aBinding.getBinding() == bBinding.getBinding();
  auto staticStorage = [](Value value) {
    if (value.getDefiningOp<memref::GetGlobalOp>())
      return true;
    auto buffer = value.getDefiningOp<bufferization::ToBufferOp>();
    return buffer && isa_and_nonnull<arith::ConstantOp>(
                         buffer->getOperand(0).getDefiningOp());
  };
  if ((aBinding && staticStorage(b)) || (bBinding && staticStorage(a)) ||
      (a.getDefiningOp<memref::AllocOp>() && (bBinding || staticStorage(b))) ||
      (b.getDefiningOp<memref::AllocOp>() && (aBinding || staticStorage(a))))
    return false;
  auto aGlobal = a.getDefiningOp<memref::GetGlobalOp>();
  auto bGlobal = b.getDefiningOp<memref::GetGlobalOp>();
  if (aGlobal && bGlobal)
    return aGlobal.getNameAttr() == bGlobal.getNameAttr();
  return !analysis.alias(lhs, rhs).isNo();
}

ModRefResult memoryAccess(Operation *op, Value target,
                          AliasAnalysis &analysis) {
  // Linalg reports operand effects; captured memory in its scalar region must
  // not be silently ignored.
  for (Region &region : op->getRegions())
    for (Operation &nested : region.getOps())
      if (!isMemoryEffectFree(&nested))
        return ModRefResult::getModAndRef();
  auto effects = getEffectsRecursively(op);
  if (!effects)
    return ModRefResult::getModAndRef();
  ModRefResult result = ModRefResult::getNoModRef();
  for (const auto &effect : *effects) {
    if (!isa<MemoryEffects::Read, MemoryEffects::Write>(effect.getEffect()))
      continue;
    if (!effect.getResource()->isAddressable())
      continue;
    if (Value value = effect.getValue(); value &&
                                         isa<MemRefType>(value.getType()) &&
                                         !mayAlias(value, target, analysis))
      continue;
    result = result.merge(isa<MemoryEffects::Write>(effect.getEffect())
                              ? ModRefResult::getMod()
                              : ModRefResult::getRef());
  }
  return result;
}

bool canFuseMVMs(MvmOp first, MvmOp next, AliasAnalysis &analysis) {
  if (first->getBlock() != next->getBlock() ||
      mayAlias(first.getSrc(), first.getDst(), analysis) ||
      mayAlias(next.getSrc(), next.getDst(), analysis))
    return false;
  for (Operation *op = first; op != next; op = op->getNextNode()) {
    if (auto mvm = dyn_cast<MvmOp>(op)) {
      // Group members write disjoint slices (or scatter back in original
      // order).
      if (mayAlias(mvm.getDst(), next.getSrc(), analysis) ||
          mayAlias(mvm.getSrc(), next.getDst(), analysis))
        return false;
    } else if (memoryAccess(op, next.getSrc(), analysis).isMod() ||
               memoryAccess(op, next.getDst(), analysis).isModOrRef()) {
      return false;
    }
  }
  return true;
}

FailureOr<SmallVector<int8_t>> readI8Elements(ElementsAttr elements) {
  if (!elements || !elements.getElementType().isInteger(8))
    return failure();
  if (auto dense = dyn_cast<DenseElementsAttr>(elements))
    return llvm::to_vector(dense.getValues<int8_t>());
  if (auto resource = dyn_cast<DenseI8ResourceElementsAttr>(elements))
    if (auto values = resource.tryGetAsArrayRef();
        values &&
        values->size() == static_cast<size_t>(elements.getNumElements()))
      return SmallVector<int8_t>(*values);
  return failure();
}

FailureOr<Value> resolveBufferBase(
    Value value,
    llvm::function_ref<LogicalResult(OpFoldResult, int64_t)> accumulate) {
  bool rebased = false;
  while (Operation *op = value.getDefiningOp()) {
    if (auto sub = dyn_cast<memref::SubViewOp>(op)) {
      if (!rebased) {
        auto sourceType = sub.getSourceType();
        SmallVector<int64_t> strides;
        int64_t offset;
        if (failed(sourceType.getStridesAndOffset(strides, offset)) ||
            llvm::any_of(strides, ShapedType::isDynamic))
          return sub.emitError("CIM subview requires static source strides"),
                 failure();
        int64_t bytes = sourceType.getElementTypeBitWidth() / 8;
        for (auto [offset, stride] :
             llvm::zip_equal(sub.getMixedOffsets(), strides)) {
          auto scale = llvm::checkedMul(stride, bytes);
          if (!scale)
            return sub.emitError("CIM view byte stride overflows"), failure();
          if (failed(accumulate(offset, *scale)))
            return failure();
        }
      }
      value = sub.getSource();
    } else if (auto reinterpret = dyn_cast<memref::ReinterpretCastOp>(op)) {
      // Reinterpret offsets replace earlier logical offsets, not byte bases.
      if (!rebased && failed(accumulate(
                          reinterpret.getMixedOffsets().front(),
                          reinterpret.getType().getElementTypeBitWidth() / 8)))
        return failure();
      rebased = true;
      value = reinterpret.getSource();
    } else if (auto view = dyn_cast<memref::ViewOp>(op)) {
      if (failed(accumulate(view.getByteShift(), 1)))
        return failure();
      rebased = false;
      value = view.getSource();
    } else if (auto view = dyn_cast<ViewLikeOpInterface>(op)) {
      value = view.getViewSource();
    } else {
      break;
    }
  }
  return value;
}

FailureOr<DenseWeight> readDenseWeight(Value value) {
  auto invalid = [&]() {
    return emitError(value.getLoc(),
                     "CIM weight requires an immutable static i8 constant "
                     "with an in-bounds strided layout"),
           failure();
  };
  auto type = cast<MemRefType>(value.getType());
  int64_t ignoredOffset;
  SmallVector<int64_t> strides;
  if (type.getRank() != 2 || !type.hasStaticShape() ||
      !type.getElementType().isInteger(8) ||
      failed(type.getStridesAndOffset(strides, ignoredOffset)) ||
      llvm::any_of(strides, [](int64_t stride) { return stride < 0; }))
    return invalid();

  int64_t offset = 0;
  auto root = resolveBufferBase(value, [&](OpFoldResult term, int64_t scale) {
    auto constant = getConstantIntValue(term);
    auto total =
        constant ? llvm::checkedMulAdd(*constant, scale, offset) : std::nullopt;
    if (!total)
      return invalid();
    offset = *total;
    return success();
  });
  if (failed(root))
    return failure();
  auto get = root->getDefiningOp<memref::GetGlobalOp>();
  auto global = get ? SymbolTable::lookupNearestSymbolFrom<memref::GlobalOp>(
                          get, get.getNameAttr())
                    : memref::GlobalOp{};
  if (!global || !global.getConstant())
    return invalid();
  auto values = readI8Elements(
      dyn_cast_or_null<ElementsAttr>(global.getInitialValueAttr()));
  int64_t k = type.getDimSize(0), n = type.getDimSize(1);
  auto count = llvm::checkedMul(k, n);
  if (failed(values) || !count || k < 1 || n < 1 || offset < 0)
    return invalid();
  int64_t last = offset;
  for (auto [size, stride] : llvm::zip_equal(type.getShape(), strides)) {
    auto end = llvm::checkedMulAdd(size - 1, stride, last);
    if (!end || *end >= static_cast<int64_t>(values->size()))
      return invalid();
    last = *end;
  }
  DenseWeight weight{k, n, {}};
  weight.data.reserve(*count);
  for (int64_t row = 0; row < k; ++row)
    for (int64_t column = 0; column < n; ++column)
      weight.data.push_back(
          (*values)[offset + row * strides[0] + column * strides[1]]);
  return weight;
}

memref::GlobalOp createDenseWeight(ModuleOp module, SymbolTable &symbols,
                                   ArrayRef<int8_t> data, int64_t k, int64_t n,
                                   StringRef name) {
  OpBuilder builder(module.getContext());
  auto tensor = RankedTensorType::get({k, n}, builder.getI8Type());
  auto global = memref::GlobalOp::create(
      builder, module.getLoc(), name, builder.getStringAttr("private"),
      MemRefType::get({k, n}, builder.getI8Type()),
      DenseElementsAttr::get(tensor, data), true, IntegerAttr());
  symbols.insert(global);
  return global;
}

Value packMVMRows(OpBuilder &builder, Value first, int64_t count, int64_t k) {
  if (auto cast = first.getDefiningOp<memref::CastOp>())
    first = cast.getSource();
  auto row = cast<memref::SubViewOp>(first.getDefiningOp());
  SmallVector<OpFoldResult> sizes(row.getMixedSizes());
  sizes[0] = builder.getIndexAttr(count);
  Value rows = memref::SubViewOp::create(builder, first.getLoc(),
                                         row.getSource(), row.getMixedOffsets(),
                                         sizes, row.getMixedStrides());
  Value flat = memref::CollapseShapeOp::create(
      builder, first.getLoc(), rows, ArrayRef<ReassociationIndices>{{0, 1}});
  return memref::ExpandShapeOp::create(builder, first.getLoc(),
                                       ArrayRef<int64_t>{1, count * k}, flat,
                                       ArrayRef<ReassociationIndices>{{0, 1}});
}

static bool areConsecutiveRows(Value previous, Value next) {
  Value a = previous;
  Value b = next;
  if (auto cast = a.getDefiningOp<memref::CastOp>())
    a = cast.getSource();
  if (auto cast = b.getDefiningOp<memref::CastOp>())
    b = cast.getSource();
  auto aRow = a.getDefiningOp<memref::SubViewOp>();
  auto bRow = b.getDefiningOp<memref::SubViewOp>();
  if (!aRow || !bRow || aRow.getSource() != bRow.getSource())
    return false;
  ArrayRef<int64_t> aOffsets = aRow.getStaticOffsets();
  ArrayRef<int64_t> bOffsets = bRow.getStaticOffsets();
  ArrayRef<int64_t> aSizes = aRow.getStaticSizes();
  ArrayRef<int64_t> bSizes = bRow.getStaticSizes();
  ArrayRef<int64_t> aStrides = aRow.getStaticStrides();
  ArrayRef<int64_t> bStrides = bRow.getStaticStrides();
  bool adjacent =
      aOffsets.size() == 2 && bOffsets.size() == 2 && aSizes[0] == 1 &&
      bSizes[0] == 1 && aSizes[1] == bSizes[1] && aOffsets[1] == 0 &&
      bOffsets[1] == 0 && bOffsets[0] == aOffsets[0] + 1 &&
      llvm::all_of(aStrides, [](int64_t stride) { return stride == 1; }) &&
      llvm::all_of(bStrides, [](int64_t stride) { return stride == 1; });
  if (!adjacent)
    return false;
  auto rowsType = memref::SubViewOp::inferResultType(
      cast<MemRefType>(aRow.getSource().getType()), aOffsets,
      ArrayRef<int64_t>{2, aSizes[1]}, aStrides);
  return memref::CollapseShapeOp::isGuaranteedCollapsible(
      rowsType, ArrayRef<ReassociationIndices>{{0, 1}});
}

bool areConsecutiveMVMRows(MvmOp previous, MvmOp next) {
  return areConsecutiveRows(previous.getSrc(), next.getSrc()) &&
         areConsecutiveRows(previous.getDst(), next.getDst());
}

Value packMVMColumns(OpBuilder &builder, Value first, int64_t columns) {
  if (auto cast = first.getDefiningOp<memref::CastOp>())
    first = cast.getSource();
  auto part = cast<memref::SubViewOp>(first.getDefiningOp());
  SmallVector<OpFoldResult> sizes(part.getMixedSizes());
  sizes[1] = builder.getIndexAttr(columns);
  return memref::SubViewOp::create(builder, first.getLoc(), part.getSource(),
                                   part.getMixedOffsets(), sizes,
                                   part.getMixedStrides());
}

bool areConsecutiveMVMColumns(MvmOp previous, MvmOp next) {
  Value a = previous.getDst();
  Value b = next.getDst();
  if (auto cast = a.getDefiningOp<memref::CastOp>())
    a = cast.getSource();
  if (auto cast = b.getDefiningOp<memref::CastOp>())
    b = cast.getSource();
  auto aPart = a.getDefiningOp<memref::SubViewOp>();
  auto bPart = b.getDefiningOp<memref::SubViewOp>();
  if (!aPart || !bPart || aPart.getSource() != bPart.getSource())
    return false;
  ArrayRef<int64_t> aOffsets = aPart.getStaticOffsets();
  ArrayRef<int64_t> bOffsets = bPart.getStaticOffsets();
  ArrayRef<int64_t> aSizes = aPart.getStaticSizes();
  ArrayRef<int64_t> bSizes = bPart.getStaticSizes();
  ArrayRef<int64_t> aStrides = aPart.getStaticStrides();
  ArrayRef<int64_t> bStrides = bPart.getStaticStrides();
  return aOffsets.size() == 2 && bOffsets.size() == 2 && aSizes[0] == 1 &&
         bSizes[0] == 1 && aOffsets[0] == bOffsets[0] &&
         bOffsets[1] == aOffsets[1] + aSizes[1] &&
         llvm::all_of(aStrides, [](int64_t stride) { return stride == 1; }) &&
         llvm::all_of(bStrides, [](int64_t stride) { return stride == 1; });
}

FailureOr<Value> flatMVMResult(OpBuilder &builder, Location loc, Value value) {
  auto type = cast<MemRefType>(value.getType());
  if (type.getRank() == 1)
    return value;
  if (type.getRank() != 2 || type.getDimSize(0) != 1)
    return failure();
  return memref::createCanonicalRankReducingSubViewOp(builder, loc, value,
                                                      {type.getDimSize(1)});
}

} // namespace mlir::iree_compiler::IREE::CIM
