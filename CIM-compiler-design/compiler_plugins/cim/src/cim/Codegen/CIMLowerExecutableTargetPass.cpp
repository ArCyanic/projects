#include "iree/compiler/Codegen/Common/PassUtils.h"
#include "iree/compiler/Codegen/Dialect/Codegen/IR/IREECodegenAttrs.h"
#include "iree/compiler/Codegen/Dialect/Codegen/IR/IREECodegenInterfaces.h"
#include "mlir/Interfaces/FunctionInterfaces.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Pass/PassManager.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMLOWEREXECUTABLETARGETPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

struct CIMLowerExecutableTargetPass
    : impl::CIMLowerExecutableTargetPassBase<CIMLowerExecutableTargetPass> {

  void runOnOperation() override {
    FunctionOpInterface funcOp = getOperation();
    auto translationInfo = getTranslationInfo(funcOp);
    if (!translationInfo)
      return;

    auto pipelineIface = cast<IREE::Codegen::PipelineAttrInterface>(
        translationInfo.getPassPipeline());
    OpPassManager pipeline = getFunctionOpInterfacePassManager(funcOp).value();
    if (failed(pipelineIface.buildPipeline(pipeline, nullptr)) ||
        failed(runPipeline(pipeline, funcOp)))
      signalPassFailure();
  }
};

} // namespace

} // namespace mlir::iree_compiler::IREE::CIM
