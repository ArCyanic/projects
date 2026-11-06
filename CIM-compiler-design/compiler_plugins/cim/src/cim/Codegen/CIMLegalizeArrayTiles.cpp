#include "iree/compiler/Codegen/Dialect/Codegen/IR/IREECodegenAttrs.h"
#include "iree/compiler/Codegen/Utils/MarkerUtils.h"
#include "iree/compiler/Codegen/Utils/Utils.h"
#include "mlir/Dialect/Linalg/IR/Linalg.h"
#include "mlir/Dialect/Linalg/IR/LinalgInterfaces.h"
#include "mlir/Dialect/SCF/IR/SCF.h"
#include "mlir/Dialect/SCF/Transforms/TileUsingInterface.h"
#include "mlir/Interfaces/FunctionInterfaces.h"
#include "mlir/Pass/Pass.h"
#include "llvm/ADT/STLExtras.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMLEGALIZEARRAYTILESPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

static FailureOr<scf::SCFTilingResult>
tile(IRRewriter &rewriter, TilingInterface op, ArrayRef<int64_t> sizes) {
  scf::SCFTilingOptions options;
  setSCFTileSizes(options, op, sizes, {});
  rewriter.setInsertionPoint(op);
  return scf::tileUsingSCF(rewriter, op, options);
}

static bool hasNonZeroTile(ArrayRef<int64_t> tiles) {
  return llvm::any_of(tiles, [](int64_t tile) { return tile > 0; });
}

static SmallVector<int64_t> tilesFor(ArrayRef<int64_t> tiles,
                                     linalg::LinalgOp op,
                                     utils::IteratorType wanted) {
  SmallVector<int64_t> result(op.getNumLoops(), 0);
  for (auto [index, type] : llvm::enumerate(op.getIteratorTypesArray())) {
    if (type == wanted && index < tiles.size())
      result[index] = tiles[index];
  }
  return result;
}

static LogicalResult
fuseElementwiseConsumers(IRRewriter &rewriter,
                         MutableArrayRef<LoopLikeOpInterface> loops) {
  if (loops.empty())
    return success();
  while (true) {
    linalg::LinalgOp consumer;
    for (Operation *user : loops.front()->getUsers()) {
      auto candidate = dyn_cast<linalg::LinalgOp>(user);
      if (!candidate || !linalg::isElementwise(candidate))
        continue;
      if (!consumer || user->isBeforeInBlock(consumer))
        consumer = candidate;
    }
    if (!consumer)
      return success();
    rewriter.setInsertionPoint(consumer);
    auto fused = scf::tileAndFuseConsumer(rewriter, consumer, loops);
    if (failed(fused) || fused->tiledOps.empty())
      return consumer.emitOpError(
          "failed to fuse elementwise consumer into array tiles");
    if (consumer->use_empty())
      rewriter.eraseOp(consumer);
  }
}

static FailureOr<linalg::LinalgOp>
tileAndFuseParallel(IRRewriter &rewriter, linalg::LinalgOp root,
                    ArrayRef<int64_t> tiles) {
  if (!hasNonZeroTile(tiles))
    return root;

  scf::SCFTilingOptions parallelTiling;
  setSCFTileSizes(parallelTiling, cast<TilingInterface>(root.getOperation()),
                  tiles, {});
  scf::SCFTileAndFuseOptions tileAndFuse;
  tileAndFuse.setTilingOptions(parallelTiling);
  rewriter.setInsertionPoint(root);
  auto parallel = scf::tileConsumerAndFuseProducersUsingSCF(
      rewriter, cast<TilingInterface>(root.getOperation()), tileAndFuse);
  if (failed(parallel) || parallel->tiledAndFusedOps.empty())
    return root.emitOpError("failed to tile parallel array dimensions");

  SmallVector<Value> replacements;
  for (Value result : root->getResults())
    replacements.push_back(parallel->replacements.lookup(result));
  rewriter.replaceOp(root, replacements);

  SmallVector<LoopLikeOpInterface> loops = parallel->loops;
  if (failed(fuseElementwiseConsumers(rewriter, loops)))
    return failure();

  auto tiledRoot =
      dyn_cast<linalg::LinalgOp>(parallel->tiledAndFusedOps.front());
  if (!tiledRoot)
    return failure();
  return tiledRoot;
}

struct CIMLegalizeArrayTilesPass final
    : impl::CIMLegalizeArrayTilesPassBase<CIMLegalizeArrayTilesPass> {

  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<linalg::LinalgDialect, scf::SCFDialect>();
  }

  void runOnOperation() override {
    FunctionOpInterface funcOp = getOperation();
    SmallVector<linalg::LinalgOp> roots;
    funcOp.walk([&](linalg::LinalgOp op) {
      if (getLoweringConfig(op))
        roots.push_back(op);
    });

    IRRewriter rewriter(&getContext());
    for (linalg::LinalgOp root : roots) {
      SmallVector<int64_t> rootTiles =
          getLoweringConfig(root).getStaticTilingLevelSizes(1, root);

      auto tiledRoot = tileAndFuseParallel(
          rewriter, root,
          tilesFor(rootTiles, root, utils::IteratorType::parallel));
      if (failed(tiledRoot))
        return signalPassFailure();

      SmallVector<int64_t> kTiles =
          tilesFor(rootTiles, *tiledRoot, utils::IteratorType::reduction);
      if (!hasNonZeroTile(kTiles))
        continue;

      auto tiled = tile(
          rewriter, cast<TilingInterface>(tiledRoot->getOperation()), kTiles);
      if (failed(tiled))
        return signalPassFailure();
      rewriter.replaceOp(*tiledRoot, tiled->replacements);
    }
    funcOp.walk([](scf::ForOp loop) { setLoopUnrollMarker(loop); });
  }
};

} // namespace

} // namespace mlir::iree_compiler::IREE::CIM
