#include "cim/Common/HardwareProfile.h"
#include "iree/compiler/Codegen/Dialect/Codegen/IR/IREECodegenAttrs.h"
#include "iree/compiler/Codegen/Dialect/Codegen/IR/IREECodegenDialect.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "iree/compiler/Dialect/LinalgExt/Utils/Utils.h"
#include "mlir/Dialect/Linalg/IR/Linalg.h"
#include "mlir/Dialect/Linalg/IR/LinalgInterfaces.h"
#include "mlir/IR/BuiltinTypes.h"
#include "mlir/Interfaces/FunctionInterfaces.h"
#include "mlir/Pass/Pass.h"
#include "llvm/Support/MathExtras.h"

#include <algorithm>

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMSELECTLOWERINGSTRATEGYPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

static int64_t uniformTileSize(int64_t size, int64_t capacity) {
  int64_t tileCount = llvm::divideCeil(size, capacity);
  while (size % tileCount)
    ++tileCount;
  return size / tileCount;
}

static FailureOr<linalg::ContractionDimensions>
getContractionDims(linalg::LinalgOp op) {
  if (op.getNumDpsInputs() < 2 || op.getNumDpsInits() < 1)
    return failure();
  SmallVector<AffineMap> maps = {
      op.getMatchingIndexingMap(op.getDpsInputOperand(0)),
      op.getMatchingIndexingMap(op.getDpsInputOperand(1)),
      op.getMatchingIndexingMap(op.getDpsInitOperand(0))};
  return linalg::inferContractionDims(maps);
}

static FailureOr<IREE::Codegen::LoweringConfigAttr>
getCIMLoweringConfig(linalg::LinalgOp root,
                     const ResolvedHardwareProfile &profile) {
  auto dims = getContractionDims(root);
  if (failed(dims) || !dims->batch.empty() || dims->m.size() != 1 ||
      dims->n.size() != 1 || dims->k.size() != 1)
    return failure();

  Type weightType = getElementTypeOrSelf(root.getDpsInputOperand(1)->get());
  if (!weightType.isInteger())
    return failure();
  int64_t columnsPerTile =
      profile.arrayColumns / weightType.getIntOrFloatBitWidth();
  if (columnsPerTile < 1)
    return failure();

  unsigned mDim = dims->m.front();
  unsigned nDim = dims->n.front();
  unsigned kDim = dims->k.front();
  SmallVector<int64_t> bounds = root.getStaticLoopRanges();
  int64_t m = bounds[mDim];
  int64_t n = bounds[nDim];
  int64_t k = bounds[kDim];
  if (ShapedType::isDynamic(m) || ShapedType::isDynamic(n) ||
      ShapedType::isDynamic(k) || m < 1 || n < 1 || k < 1)
    return failure();

  int64_t kTile = uniformTileSize(k, profile.arrayRows);
  int64_t nTile = uniformTileSize(n, columnsPerTile);
  int64_t mCap =
      std::min({m, profile.arrayRows / kTile, columnsPerTile / nTile});
  if (mCap < 1)
    return failure();
  int64_t mTile = uniformTileSize(m, mCap);

  SmallVector<int64_t> workgroup(root.getNumLoops(), 0);
  SmallVector<int64_t> array(root.getNumLoops(), 0);
  workgroup[mDim] = mTile;
  array[mDim] = 1;
  array[nDim] = nTile;
  array[kDim] = kTile;
  return IREE::Codegen::LoweringConfigAttr::get(root->getContext(),
                                                {workgroup, array});
}

struct CIMSelectLoweringStrategyPass final
    : impl::CIMSelectLoweringStrategyPassBase<CIMSelectLoweringStrategyPass> {

  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<IREE::Codegen::IREECodegenDialect, linalg::LinalgDialect>();
  }

  void runOnOperation() override {
    MLIRContext *context = &getContext();
    auto defaultInfo = IREE::Codegen::TranslationInfoAttr::get(
        context, IREE::Codegen::PassPipelineAttr::get(context, "cim-workgroup"),
        /*codegenSpec=*/nullptr, /*workgroupSize=*/{}, /*subgroupSize=*/0,
        Builder(context).getDictionaryAttr({}));

    for (auto funcOp : getOperation().getOps<FunctionOpInterface>()) {
      if (getTranslationInfo(funcOp))
        continue;

      auto profile = resolveHardwareProfile(funcOp);
      if (failed(profile))
        return signalPassFailure();

      auto walkResult = funcOp.walk([&](linalg::LinalgOp root) {
        if (!linalg::isaContractionOpInterface(root) &&
            !IREE::LinalgExt::isaHorizontallyFusedContraction(root)) {
          return WalkResult::advance();
        }
        auto config = getCIMLoweringConfig(root, *profile);
        if (failed(config)) {
          root.emitOpError("failed to compute CIM lowering_config");
          signalPassFailure();
          return WalkResult::interrupt();
        }
        if (failed(setOpConfigAndEntryPointFnTranslation(funcOp, root, *config,
                                                         defaultInfo))) {
          signalPassFailure();
          return WalkResult::interrupt();
        }
        return WalkResult::advance();
      });
      if (walkResult.wasInterrupted())
        return;
    }
  }
};

} // namespace

} // namespace mlir::iree_compiler::IREE::CIM
