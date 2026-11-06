#include "cim/Codegen/CIMMVMUtils.h"
#include "cim/Codegen/CIMPasses.h"
#include "cim/Common/HardwareProfile.h"

#include "mlir/Analysis/SliceAnalysis.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Linalg/IR/Linalg.h"
#include "mlir/Dialect/Linalg/IR/LinalgInterfaces.h"
#include "mlir/Dialect/Tensor/IR/Tensor.h"
#include "mlir/IR/Dominance.h"
#include "mlir/IR/Matchers.h"
#include "mlir/IR/PatternMatch.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Transforms/RegionUtils.h"
#include "llvm/ADT/MapVector.h"
#include "llvm/ADT/STLExtras.h"
#include "llvm/Support/MathExtras.h"

#include <tuple>

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMFUSEHETEROGENEOUSCONTRACTIONSPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

struct MVMCandidate {
  linalg::LinalgOp op;
  Value activation;
  const DenseWeight &weight;
  int64_t m;
  SetVector<Operation *> dependencies;
  unsigned depth = 0;
};

using WeightInventory = llvm::MapVector<Operation *, DenseWeight>;
using CandidateGroup = SmallVector<const MVMCandidate *>;

static std::optional<DenseWeight> readStaticWeight(linalg::LinalgOp op) {
  auto dims = linalg::inferContractionDims(op);
  if (failed(dims) || !dims->batch.empty() || dims->m.size() != 1 ||
      dims->n.size() != 1 || dims->k.size() != 1)
    return std::nullopt;

  SmallVector<int64_t> bounds = op.getStaticLoopRanges();
  int64_t k = bounds[dims->k.front()];
  int64_t n = bounds[dims->n.front()];
  if (ShapedType::isDynamic(k) || ShapedType::isDynamic(n) || k < 1 || n < 1)
    return std::nullopt;

  Value source = op.getDpsInputOperand(1)->get();
  auto weightType = dyn_cast<RankedTensorType>(source.getType());
  if (!weightType || weightType.getRank() != 2 ||
      !weightType.hasStaticShape() || !weightType.getElementType().isInteger(8))
    return std::nullopt;

  AffineMap rhsMap = op.getMatchingIndexingMap(op.getDpsInputOperand(1));
  auto kAxis = rhsMap.getResultPosition(
      getAffineDimExpr(dims->k.front(), op.getContext()));
  auto nAxis = rhsMap.getResultPosition(
      getAffineDimExpr(dims->n.front(), op.getContext()));
  if (!kAxis || !nAxis)
    return std::nullopt;
  bool mapTransposed = *kAxis == 1 && *nAxis == 0;
  if (!mapTransposed && (*kAxis != 0 || *nAxis != 1))
    return std::nullopt;

  bool transposed = false;
  if (auto transpose = source.getDefiningOp<linalg::TransposeOp>()) {
    if (transpose.getPermutation() != ArrayRef<int64_t>{1, 0})
      return std::nullopt;
    source = transpose.getInput();
    transposed = true;
  }
  transposed ^= mapTransposed;

  auto constant = source.getDefiningOp<arith::ConstantOp>();
  auto elements =
      constant ? dyn_cast<ElementsAttr>(constant.getValue()) : nullptr;
  if (!elements ||
      cast<ShapedType>(elements.getType()).getShape() !=
          ArrayRef<int64_t>{transposed ? n : k, transposed ? k : n})
    return std::nullopt;

  auto values = readI8Elements(elements);
  if (failed(values))
    return std::nullopt;
  DenseWeight result{k, n, SmallVector<int8_t>(k * n)};
  for (int64_t row = 0; row < k; ++row)
    for (int64_t column = 0; column < n; ++column)
      result.data[row * n + column] = transposed ? (*values)[column * k + row]
                                                 : (*values)[row * n + column];
  return result;
}

static std::optional<MVMCandidate> matchCandidate(linalg::LinalgOp op,
                                                  const DenseWeight &weight) {
  if (!isSignedContraction(op) || op.getNumDpsInputs() != 2 ||
      op.getNumDpsInits() != 1 || op->getNumResults() != 1)
    return std::nullopt;

  auto dims = linalg::inferContractionDims(op);
  if (failed(dims) || !dims->batch.empty() || dims->m.size() != 1 ||
      dims->n.size() != 1 || dims->k.size() != 1)
    return std::nullopt;
  SmallVector<int64_t> bounds = op.getStaticLoopRanges();
  int64_t m = bounds[dims->m.front()];
  if (ShapedType::isDynamic(m) || m < 1)
    return std::nullopt;

  auto mExpr = getAffineDimExpr(dims->m.front(), op.getContext());
  auto kExpr = getAffineDimExpr(dims->k.front(), op.getContext());
  auto nExpr = getAffineDimExpr(dims->n.front(), op.getContext());
  if (op.getMatchingIndexingMap(op.getDpsInputOperand(0)).getResults() !=
          ArrayRef<AffineExpr>{mExpr, kExpr} ||
      op.getMatchingIndexingMap(op.getDpsInitOperand(0)).getResults() !=
          ArrayRef<AffineExpr>{mExpr, nExpr})
    return std::nullopt;

  Value activation = op.getDpsInputOperand(0)->get();
  auto activationType = dyn_cast<RankedTensorType>(activation.getType());
  auto resultType = dyn_cast<RankedTensorType>(op->getResult(0).getType());
  if (!activationType || !resultType || activationType.getRank() != 2 ||
      resultType.getRank() != 2 || !activationType.hasStaticShape() ||
      !resultType.hasStaticShape() ||
      resultType.getShape() != ArrayRef<int64_t>{m, weight.n})
    return std::nullopt;

  auto fill = op.getDpsInitOperand(0)->get().getDefiningOp<linalg::FillOp>();
  if (!fill || !matchPattern(fill.getInputs().front(), m_Zero()))
    return std::nullopt;

  return MVMCandidate{op, activation, weight, m, {}};
}

static LogicalResult
analyzeDependencies(MutableArrayRef<MVMCandidate> candidates) {
  for (MVMCandidate &candidate : candidates) {
    BackwardSliceOptions options;
    options.omitBlockArguments = true;
    options.filter = [block = candidate.op->getBlock()](Operation *op) {
      return op->getBlock() == block;
    };
    if (failed(
            getBackwardSlice(candidate.op, &candidate.dependencies, options)))
      return failure();
  }
  // SSA definitions precede their users in each block. The slices are
  // block-local, so reverse IR order computes consumer depths before their
  // producers.
  for (const MVMCandidate &consumer : llvm::reverse(candidates))
    for (MVMCandidate &producer : candidates)
      if (consumer.dependencies.contains(producer.op))
        producer.depth = std::max(producer.depth, consumer.depth + 1);
  return success();
}

static bool compatible(const MVMCandidate &candidate,
                       ArrayRef<const MVMCandidate *> group) {
  if (candidate.op->getBlock() != group.front()->op->getBlock() ||
      candidate.m != group.front()->m ||
      getElementTypeOrSelf(candidate.activation.getType()) !=
          getElementTypeOrSelf(group.front()->activation.getType()) ||
      getElementTypeOrSelf(candidate.op->getResult(0).getType()) !=
          getElementTypeOrSelf(group.front()->op->getResult(0).getType()))
    return false;

  for (const MVMCandidate *other : group) {
    if (candidate.activation == other->activation ||
        candidate.dependencies.contains(other->op) ||
        other->dependencies.contains(candidate.op))
      return false;
  }
  return true;
}

// Lexicographic policy: save more windows, prefer consumers, then larger
// groups.
static std::tuple<int64_t, int64_t, size_t>
scoreGroup(ArrayRef<const MVMCandidate *> group, int64_t arrayColumns) {
  int64_t originalWindows = 0, totalColumns = 0, depthSum = 0;
  for (const MVMCandidate *candidate : group) {
    originalWindows += llvm::divideCeil(candidate->weight.n, arrayColumns);
    totalColumns += candidate->weight.n;
    depthSum += candidate->depth;
  }
  return {originalWindows - llvm::divideCeil(totalColumns, arrayColumns),
          -depthSum, group.size()};
}

static DenseWeight buildGroupWeight(ArrayRef<const MVMCandidate *> group) {
  auto weights = llvm::map_to_vector(
      group, [](const MVMCandidate *candidate) { return &candidate->weight; });
  return DenseWeight::blockDiagonal(weights);
}

static bool isFeasibleGroup(const WeightInventory &weights,
                            ArrayRef<const MVMCandidate *> group,
                            const ResolvedHardwareProfile &profile) {
  int64_t rows = 0;
  for (const MVMCandidate *candidate : group)
    rows += candidate->weight.k;
  if (rows > profile.arrayRows)
    return false;
  SmallVector<const DenseWeight *> inventory;
  for (const auto &[op, weight] : weights)
    if (llvm::none_of(group, [operation = op](const MVMCandidate *member) {
          return member->op == operation;
        }))
      inventory.push_back(&weight);
  DenseWeight fused = buildGroupWeight(group);
  inventory.push_back(&fused);
  auto plan =
      planStaticArray(inventory, profile.arrayRows, profile.arrayCellColumns());
  if (!plan) {
    llvm::consumeError(plan.takeError());
    return false;
  }
  return true;
}

static CandidateGroup growGroup(
    const MVMCandidate *seed, ArrayRef<const MVMCandidate *> orderedCandidates,
    const WeightInventory &weights, const ResolvedHardwareProfile &profile) {
  CandidateGroup group{seed};
  while (true) {
    const MVMCandidate *bestAddition = nullptr;
    int64_t bestSavings =
        std::get<0>(scoreGroup(group, profile.arrayCellColumns())) - 1;
    for (const MVMCandidate *candidate : orderedCandidates) {
      if (llvm::is_contained(group, candidate) ||
          !compatible(*candidate, group))
        continue;
      CandidateGroup trial(group);
      trial.push_back(candidate);
      int64_t savings =
          std::get<0>(scoreGroup(trial, profile.arrayCellColumns()));
      // The current group's savings are constant across additions. Ignore ties
      // before placement, preserving the first candidate in the stable order.
      if (savings <= bestSavings || !isFeasibleGroup(weights, trial, profile))
        continue;
      bestSavings = savings;
      bestAddition = candidate;
    }
    if (!bestAddition)
      return group;
    group.push_back(bestAddition);
  }
}

static CandidateGroup selectBestGroup(ArrayRef<MVMCandidate> candidates,
                                      const WeightInventory &weights,
                                      const ResolvedHardwareProfile &profile) {
  SmallVector<const MVMCandidate *> ordered;
  for (const MVMCandidate &candidate : candidates)
    ordered.push_back(&candidate);
  llvm::stable_sort(ordered,
                    [](const MVMCandidate *lhs, const MVMCandidate *rhs) {
                      return lhs->depth < rhs->depth;
                    });

  CandidateGroup best;
  int64_t arrayColumns = profile.arrayCellColumns();
  for (const MVMCandidate *seed : ordered) {
    CandidateGroup group = growGroup(seed, ordered, weights, profile);
    auto score = scoreGroup(group, arrayColumns);
    if (group.size() > 1 && std::get<0>(score) > 0 &&
        (best.empty() || score > scoreGroup(best, arrayColumns)))
      best = std::move(group);
  }
  return best;
}

static LogicalResult rewriteGroup(RewriterBase &rewriter,
                                  ArrayRef<const MVMCandidate *> group,
                                  DominanceInfo &dominanceInfo) {
  SmallVector<Value> activations;
  Operation *insertionPoint = group.front()->op;
  for (const MVMCandidate *candidate : group) {
    activations.push_back(candidate->activation);
    if (candidate->op->isBeforeInBlock(insertionPoint))
      insertionPoint = candidate->op;
  }
  rewriter.setInsertionPoint(insertionPoint);
  if (failed(moveValueDefinitions(rewriter, activations, insertionPoint,
                                  dominanceInfo)))
    return failure();

  DenseWeight fusedWeight = buildGroupWeight(group);
  Location loc = insertionPoint->getLoc();
  auto blockType = RankedTensorType::get({fusedWeight.k, fusedWeight.n},
                                         rewriter.getI8Type());
  Value block = arith::ConstantOp::create(
      rewriter, loc,
      DenseElementsAttr::get(blockType, ArrayRef<int8_t>(fusedWeight.data)));

  Value packed =
      tensor::ConcatOp::create(rewriter, loc, /*dim=*/1, activations);

  auto resultElement =
      cast<RankedTensorType>(group.front()->op->getResult(0).getType())
          .getElementType();
  auto resultType =
      RankedTensorType::get({group.front()->m, fusedWeight.n}, resultElement);
  Value empty = tensor::EmptyOp::create(rewriter, loc, resultType.getShape(),
                                        resultElement);
  Value zero = arith::ConstantOp::create(rewriter, loc,
                                         rewriter.getZeroAttr(resultElement));
  Value init = linalg::FillOp::create(rewriter, loc, ValueRange{zero}, empty)
                   .getResult(0);
  Value result = linalg::MatmulOp::create(rewriter, loc, resultType,
                                          ValueRange{packed, block}, init)
                     .getResult(0);

  rewriter.setInsertionPointAfter(result.getDefiningOp());
  SmallVector<Value> slices;
  slices.reserve(group.size());
  int64_t nOffset = 0;
  for (const MVMCandidate *candidate : group) {
    slices.push_back(tensor::ExtractSliceOp::create(
        rewriter, loc,
        cast<RankedTensorType>(candidate->op->getResult(0).getType()), result,
        getAsOpFoldResult(rewriter.getI64ArrayAttr({0, nOffset})),
        getAsOpFoldResult(
            rewriter.getI64ArrayAttr({candidate->m, candidate->weight.n})),
        getAsOpFoldResult(rewriter.getI64ArrayAttr({1, 1}))));
    nOffset += candidate->weight.n;
  }
  for (auto [candidate, slice] : llvm::zip_equal(group, slices))
    rewriter.replaceOp(candidate->op, slice);
  return success();
}

struct CIMFuseHeterogeneousContractionsPass final
    : impl::CIMFuseHeterogeneousContractionsPassBase<
          CIMFuseHeterogeneousContractionsPass> {
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<arith::ArithDialect, linalg::LinalgDialect,
                    tensor::TensorDialect>();
  }

  void runOnOperation() override {
    ModuleOp module = getOperation();
    ResolvedHardwareProfile profile = getCompetitionHardwareProfile();
    IRRewriter rewriter(&getContext());
    while (true) {
      // This inventory is immutable until rewriteGroup. Candidate references
      // remain valid and every trial sees the same complete deployment.
      WeightInventory weights;
      module.walk([&](linalg::LinalgOp op) {
        if (auto weight = readStaticWeight(op))
          weights.insert({op, std::move(*weight)});
      });
      SmallVector<MVMCandidate> candidates;
      for (const auto &[op, weight] : weights)
        if (auto candidate = matchCandidate(cast<linalg::LinalgOp>(op), weight))
          candidates.push_back(std::move(*candidate));
      if (candidates.empty())
        return;
      if (failed(analyzeDependencies(candidates)))
        return signalPassFailure();

      CandidateGroup group = selectBestGroup(candidates, weights, profile);
      if (group.empty())
        return;

      DominanceInfo dominanceInfo(module);
      if (failed(rewriteGroup(rewriter, group, dominanceInfo)))
        return signalPassFailure();
    }
  }
};

} // namespace
} // namespace mlir::iree_compiler::IREE::CIM
