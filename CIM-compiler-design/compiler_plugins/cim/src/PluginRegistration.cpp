#include "cim/Codegen/CIMPasses.h"
#include "cim/Frontend/CIMNormalizeONNXLinear.h"
#include "cim/IR/CIMDialect.h"
#include "cim/Target/CIMCompilerOptions.h"
#include "cim/Target/CIMTargetBackend.h"
#include "iree/compiler/Dialect/HAL/Target/TargetRegistry.h"
#include "iree/compiler/Dialect/Util/IR/UtilOps.h"
#include "iree/compiler/DispatchCreation/Passes.h"
#include "iree/compiler/PluginAPI/Client.h"
#include "iree/compiler/Utils/PassUtils.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/DialectRegistry.h"
#include "torch-mlir/Dialect/Torch/IR/TorchDialect.h"

#include <memory>

using namespace mlir;
using namespace mlir::iree_compiler;

namespace {

struct CIMSession : public PluginSession<CIMSession, IREE::CIM::CIMOptions> {
  static void registerPasses() {
    IREE::CIM::registerCIMCodegenPasses();
    IREE::CIM::registerCIMFrontendPasses();
  }

  void onRegisterDialects(DialectRegistry &registry) override {
    registry.insert<IREE::CIM::CIMDialect, torch::Torch::TorchDialect>();
  }

  LogicalResult onActivate() override { return success(); }

  void extendInputConversionPreprocessingPassPipeline(
      OpPassManager &passManager,
      InputDialectOptions::Type /*inputType*/) override {
    passManager.addPass(IREE::CIM::createCIMNormalizeONNXLinearPass());
  }

  void extendPreprocessingPassPipeline(OpPassManager &passManager) override {
    if (options.optimizationPipeline ==
            IREE::CIM::OptimizationPipeline::Heterogeneous ||
        options.optimizationPipeline ==
            IREE::CIM::OptimizationPipeline::Replicated)
      passManager.addPass(
          IREE::CIM::createCIMFuseHeterogeneousContractionsPass());

    DispatchCreation::FuseHorizontalContractionsPassOptions fusionOptions;
    fusionOptions.fusionLimit = 4;
    MultiOpNest<func::FuncOp, IREE::Util::InitializerOp, IREE::Util::FuncOp>(
        passManager)
        .addPass([fusionOptions] {
          return DispatchCreation::createFuseHorizontalContractionsPass(
              fusionOptions);
        });
  }

  void
  populateHALTargetBackends(IREE::HAL::TargetBackendList &targets) override {
    targets.add("cim", [=]() {
      return std::make_shared<IREE::CIM::CIMTargetBackend>(options);
    });
  }
};

} // namespace

extern "C" bool iree_register_compiler_plugin_cim(
    mlir::iree_compiler::PluginRegistrar *registrar) {
  registrar->registerPlugin<CIMSession>("cim");
  return true;
}
