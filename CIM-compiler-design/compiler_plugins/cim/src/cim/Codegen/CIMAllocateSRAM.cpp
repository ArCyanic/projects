#include "cim/Codegen/CIMPasses.h"

#include "cim/Common/HardwareProfile.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Bufferization/Transforms/Passes.h"
#include "mlir/Dialect/Bufferization/Transforms/StaticMemoryPlanning.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/Pass/Pass.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DECL_CIMALLOCATESRAMPASS
#define GEN_PASS_DEF_CIMALLOCATESRAMPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

struct CIMAllocateSRAMPass final
    : impl::CIMAllocateSRAMPassBase<CIMAllocateSRAMPass> {
  using Base::Base;
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<arith::ArithDialect, memref::MemRefDialect>();
  }

  void runOnOperation() override {
    for (auto variant : cimVariants(getOperation())) {
      auto profile = resolveHardwareProfile(variant);
      if (failed(profile))
        return signalPassFailure();
      for (auto func : variant.getInnerModule().getOps<func::FuncOp>()) {
        SmallVector<memref::AllocOp> allocs;
        func.walk([&](memref::AllocOp alloc) { allocs.push_back(alloc); });
        if (allocs.empty())
          continue;
        if (!llvm::hasSingleElement(func.getBody())) {
          func.emitError("CIM SRAM planning requires a straight-line entry");
          return signalPassFailure();
        }
        OpBuilder builder(func.getBody().front().getTerminator());
        for (memref::AllocOp alloc : allocs) {
          if (alloc->getBlock() != &func.getBody().front() ||
              !alloc.getType().hasStaticShape()) {
            alloc.emitError(
                "CIM SRAM allocation requires a static entry buffer");
            return signalPassFailure();
          }
          alloc.setAlignment(profile->sramAlignmentBytes);
          memref::DeallocOp::create(builder, alloc.getLoc(), alloc);
        }

        OpPassManager pipeline(func::FuncOp::getOperationName());
        if (reuse)
          pipeline.addPass(
              bufferization::createOptimizeAllocationLivenessPass());
        bufferization::StaticMemoryPlannerAnalysisPassOptions options;
        options.algorithm =
            reuse ? bufferization::MemoryPlannerAlgorithm::BestFit
                  : bufferization::MemoryPlannerAlgorithm::Trivial;
        pipeline.addPass(
            bufferization::createStaticMemoryPlannerAnalysisPass(options));
        if (failed(runPipeline(pipeline, func)))
          return signalPassFailure();
        for (auto arena : func.getOps<memref::AllocOp>()) {
          if (arena.getType().getNumElements() > profile->sramCapacityBytes) {
            func.emitError("CIM SRAM plan exceeds profile capacity");
            return signalPassFailure();
          }
        }
      }
    }
  }
};

} // namespace
} // namespace mlir::iree_compiler::IREE::CIM
