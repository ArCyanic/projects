#include "cim/Codegen/CIMMVMUtils.h"
#include "cim/Codegen/CIMPasses.h"
#include "cim/Codegen/StaticArrayPlacement.h"
#include "cim/Common/HardwareProfile.h"
#include "iree/compiler/Dialect/HAL/IR/HALDialect.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/Pass/Pass.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMPACKHORIZONTALMVMSPASS
#define GEN_PASS_DEF_CIMREPLICATEWEIGHTMVMSPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

struct LogicalMVM {
  MvmOp op;
  DenseWeight weight;
};

static LogicalResult collectMVMs(ModuleOp module,
                                 SmallVectorImpl<LogicalMVM> &mvms) {
  return failure(module
                     .walk([&](MvmOp op) -> WalkResult {
                       auto weight = readDenseWeight(op.getWeight());
                       if (failed(weight))
                         return WalkResult::interrupt();
                       mvms.push_back({op, std::move(*weight)});
                       return WalkResult::advance();
                     })
                     .wasInterrupted());
}

// The use list is the inventory: retaining any old use retains its weight in
// the planner's content-based deduplication. No IR is changed during a trial.
static bool fitsReplacement(ArrayRef<LogicalMVM> mvms, unsigned begin,
                            unsigned end, const DenseWeight &replacement,
                            int64_t rows, int64_t columns) {
  SmallVector<const DenseWeight *> weights;
  for (auto [index, mvm] : llvm::enumerate(mvms)) {
    if (index == begin)
      weights.push_back(&replacement);
    else if ((index < begin || index >= end) && mvm.op)
      weights.push_back(&mvm.weight);
  }
  auto plan = planStaticArray(weights, rows, columns);
  if (!plan) {
    llvm::consumeError(plan.takeError());
    return false;
  }
  return true;
}

static Value weightValue(OpBuilder &builder, Location loc,
                         memref::GlobalOp global) {
  return memref::GetGlobalOp::create(builder, loc, global.getType(),
                                     global.getNameAttr());
}

static LogicalResult packHorizontal(ModuleOp module, int64_t arrayRows,
                                    int64_t arrayColumns) {
  SymbolTable symbols(module);
  AliasAnalysis aliases(module);
  SmallVector<LogicalMVM> mvms;
  if (failed(collectMVMs(module, mvms)))
    return failure();
  for (unsigned begin = 0; begin < mvms.size();) {
    unsigned end = begin + 1;
    int64_t n = mvms[begin].weight.n;
    while (end < mvms.size() &&
           mvms[end].op->getParentOp() == mvms[begin].op->getParentOp() &&
           mvms[end].op.getSrc() == mvms[begin].op.getSrc() &&
           n + mvms[end].weight.n <= arrayColumns &&
           canFuseMVMs(mvms[begin].op, mvms[end].op, aliases)) {
      n += mvms[end].weight.n;
      ++end;
    }
    if (end == begin + 1) {
      begin = end;
      continue;
    }

    int64_t k = mvms[begin].weight.k;
    SmallVector<int8_t> data;
    data.reserve(k * n);
    for (int64_t row = 0; row < k; ++row)
      for (const LogicalMVM &mvm : ArrayRef(mvms).slice(begin, end - begin))
        llvm::append_range(
            data,
            ArrayRef(mvm.weight.data).slice(row * mvm.weight.n, mvm.weight.n));

    DenseWeight formed{k, n, std::move(data)};
    if (!fitsReplacement(mvms, begin, end, formed, arrayRows, arrayColumns)) {
      // Keep the first MVM and try the remaining suffix as a smaller group.
      ++begin;
      continue;
    }
    auto global = createDenseWeight(module, symbols, formed.data, k, n);
    MvmOp first = mvms[begin].op;
    OpBuilder builder(first);
    bool consecutive = true;
    for (unsigned i = begin + 1; i < end; ++i)
      consecutive &= areConsecutiveMVMColumns(mvms[i - 1].op, mvms[i].op);
    Value packed = consecutive
                       ? packMVMColumns(builder, first.getDst(), n)
                       : memref::AllocOp::create(
                             builder, first.getLoc(),
                             MemRefType::get({1, n}, builder.getI32Type()));
    auto fused =
        MvmOp::create(builder, first.getLoc(), first.getSrc(),
                      weightValue(builder, first.getLoc(), global), packed);
    int64_t offset = 0;
    for (unsigned i = begin; !consecutive && i < end; ++i) {
      MvmOp old = mvms[i].op;
      OpBuilder store(old);
      Value view = memref::SubViewOp::create(
          store, old.getLoc(), packed, ArrayRef<int64_t>{0, offset},
          ArrayRef<int64_t>{1, mvms[i].weight.n}, ArrayRef<int64_t>{1, 1});
      memref::CopyOp::create(store, old.getLoc(), view, old.getDst());
      offset += mvms[i].weight.n;
    }
    for (unsigned i = begin; i < end; ++i) {
      mvms[i].op.erase();
      mvms[i].op = {};
    }
    mvms[begin] = {fused, std::move(formed)};
    begin = end;
  }
  return success();
}

static bool sameWeight(const DenseWeight &a, const DenseWeight &b) {
  return a.k == b.k && a.n == b.n && a.data == b.data;
}

static LogicalResult replicateRows(ModuleOp module, int64_t arrayRows,
                                   int64_t arrayColumns) {
  SymbolTable symbols(module);
  AliasAnalysis aliases(module);
  SmallVector<LogicalMVM> mvms;
  if (failed(collectMVMs(module, mvms)))
    return failure();
  for (unsigned begin = 0; begin < mvms.size();) {
    unsigned end = begin + 1;
    while (end < mvms.size() &&
           mvms[end].op->getParentOp() == mvms[begin].op->getParentOp() &&
           sameWeight(mvms[end].weight, mvms[begin].weight) &&
           areConsecutiveMVMRows(mvms[end - 1].op, mvms[end].op) &&
           canFuseMVMs(mvms[begin].op, mvms[end].op, aliases))
      ++end;

    DenseWeight weight = mvms[begin].weight;
    int64_t factor = std::min<int64_t>(
        {end - begin, arrayRows / weight.k, arrayColumns / weight.n});
    if (factor < 2) {
      begin = end;
      continue;
    }

    for (unsigned chunk = begin; chunk < end;) {
      int64_t count = std::min<int64_t>(factor, end - chunk);
      DenseWeight block;
      for (; count > 1; --count) {
        SmallVector<const DenseWeight *> copies(count, &weight);
        block = DenseWeight::blockDiagonal(copies);
        if (fitsReplacement(mvms, chunk, chunk + count, block, arrayRows,
                            arrayColumns))
          break;
      }
      if (count == 1) {
        ++chunk;
        continue;
      }
      auto global =
          createDenseWeight(module, symbols, block.data, block.k, block.n);
      MvmOp first = mvms[chunk].op;
      OpBuilder builder(first);
      Value activation = packMVMRows(builder, first.getSrc(), count, weight.k);
      Value packed = packMVMRows(builder, first.getDst(), count, weight.n);
      auto fused =
          MvmOp::create(builder, first.getLoc(), activation,
                        weightValue(builder, first.getLoc(), global), packed);
      for (int64_t i = 0; i < count; ++i) {
        mvms[chunk + i].op.erase();
        mvms[chunk + i].op = {};
      }
      mvms[chunk] = {fused, std::move(block)};
      chunk += count;
    }
    begin = end;
  }
  return success();
}

struct CIMPackHorizontalMVMsPass final
    : impl::CIMPackHorizontalMVMsPassBase<CIMPackHorizontalMVMsPass> {
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<IREE::CIM::CIMDialect, IREE::HAL::HALDialect,
                    memref::MemRefDialect>();
  }
  void runOnOperation() override {
    for (auto variant : cimVariants(getOperation())) {
      auto profile = resolveHardwareProfile(variant);
      if (failed(profile))
        return signalPassFailure();
      int64_t columns = profile->arrayCellColumns();
      if (failed(packHorizontal(variant.getInnerModule(), profile->arrayRows,
                                columns)))
        return signalPassFailure();
    }
  }
};

struct CIMReplicateWeightMVMsPass final
    : impl::CIMReplicateWeightMVMsPassBase<CIMReplicateWeightMVMsPass> {
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<IREE::CIM::CIMDialect, IREE::HAL::HALDialect,
                    memref::MemRefDialect>();
  }
  void runOnOperation() override {
    for (auto variant : cimVariants(getOperation())) {
      auto profile = resolveHardwareProfile(variant);
      if (failed(profile))
        return signalPassFailure();
      int64_t columns = profile->arrayCellColumns();
      if (failed(replicateRows(variant.getInnerModule(), profile->arrayRows,
                               columns)))
        return signalPassFailure();
    }
  }
};

} // namespace
} // namespace mlir::iree_compiler::IREE::CIM
