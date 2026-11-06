#include "cim/Codegen/CIMPasses.h"

#include "iree/compiler/Codegen/Common/GPU/Passes.h"
#include "iree/compiler/Codegen/Common/PassUtils.h"
#include "iree/compiler/Codegen/Common/Passes.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "iree/compiler/Dialect/Util/Transforms/Passes.h"
#include "iree/compiler/Transforms/Passes.h"
#include "mlir/Dialect/Linalg/Passes.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Pass/PassRegistry.h"
#include "mlir/Transforms/Passes.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DECL
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

void buildCIMPipeline(OpPassManager &pm) {
  pm.addPass(createTileAndDistributeToWorkgroupsUsingForallOpPass());
  pm.addPass(createDecomposeLinalgGenericPass());
  pm.addPass(createCIMLegalizeArrayTilesPass());
  pm.addPass(createDecomposeHorizontallyFusedGemmsPass());
  pm.addPass(createCanonicalizerPass());
  pm.addPass(createBufferizeDispatchTensorLoadStorePass());
  pm.addPass(createCanonicalizerPass());
  pm.addPass(createCSEPass());
  addIREEComprehensiveBufferizePasses(pm);
  pm.addPass(createRemoveSingleIterationLoopPass());
  pm.addPass(createEraseHALDescriptorTypeFromMemRefPass());
  pm.addPass(createCIMConvertLinalgToCIMPass());
  pm.addPass(createCanonicalizerPass());
  pm.addPass(createCSEPass());
}

} // namespace

namespace {
#define GEN_PASS_REGISTRATION
#include "cim/Codegen/CIMPasses.h.inc"
} // namespace

void registerCIMCodegenPasses() {
  registerPasses();
  static PassPipelineRegistration<> pipeline(
      "cim-workgroup", "Lower a workgroup to logical CIM operations",
      buildCIMPipeline);
}

SmallVector<IREE::HAL::ExecutableVariantOp> cimVariants(ModuleOp module) {
  SmallVector<IREE::HAL::ExecutableVariantOp> variants;
  for (auto executable : module.getOps<IREE::HAL::ExecutableOp>())
    for (auto variant : executable.getOps<IREE::HAL::ExecutableVariantOp>())
      if (variant.getTarget().getBackend().getValue() == "cim")
        variants.push_back(variant);
  return variants;
}

void buildCIMCodegenConfigurationPassPipeline(
    OpPassManager &modulePassManager) {
  {
    FunctionLikeNest funcPassManager(modulePassManager);
    addCommonTargetExecutablePreprocessingPasses(funcPassManager);
  }
  modulePassManager.addPass(createMaterializeUserConfigsPass());
  FunctionLikeNest(modulePassManager)
      .addPass(createMaterializeDeviceEncodingPass);
  modulePassManager.addPass(createCIMSelectLoweringStrategyPass());
}

void buildCIMCodegenTranslationPassPipeline(OpPassManager &modulePassManager) {
  FunctionLikeNest(modulePassManager)
      .addPass(createCIMLowerExecutableTargetPass);
  modulePassManager.addPass(createReconcileTranslationInfoPass());
  modulePassManager.addPass(createResolveWorkgroupCountHintsPass());
  modulePassManager.addPass(createIREEBufferizeConstantsPass());
  modulePassManager.addPass(IREE::Util::createDropCompilerHintsPass());
  modulePassManager.addPass(createCIMConvertToTargetIRPass());
  modulePassManager.addPass(createCanonicalizerPass());
  FunctionLikeNest(modulePassManager).addPass(createUnrollAnnotatedLoopsPass);
  modulePassManager.addPass(createCanonicalizerPass());
  modulePassManager.addPass(createCSEPass());
}

void buildCIMLinkingPassPipeline(OpPassManager &modulePassManager,
                                 OptimizationPipeline pipeline,
                                 SRAMAllocation sramAllocation,
                                 StringRef dumpPhysicalizationTo) {
  // The contest asks for the intermediate result of every deployment stage.
  // IREE's own `--dump-compilation-phases-to` stops at the HAL boundary, so
  // the CIM physicalization stages dump themselves.
  unsigned stage = 0;
  auto dump = [&](StringRef label) {
    if (dumpPhysicalizationTo.empty())
      return;
    CIMDumpPhysicalizationPassOptions options;
    options.path = dumpPhysicalizationTo.str();
    options.label = (llvm::Twine(++stage) + "." + label).str();
    modulePassManager.addPass(createCIMDumpPhysicalizationPass(options));
  };

  modulePassManager.addPass(createCIMLinkExecutablesPass());
  dump("linked");
  if (pipeline != OptimizationPipeline::Direct) {
    modulePassManager.addPass(createCIMPackHorizontalMVMsPass());
    dump("packed");
  }
  if (pipeline == OptimizationPipeline::Replicated) {
    modulePassManager.addPass(createCanonicalizerPass());
    modulePassManager.addPass(createCIMReplicateWeightMVMsPass());
    dump("replicated");
  }
  modulePassManager.addPass(createCIMPlanArrayPass());
  dump("array-planned");
  modulePassManager.addPass(createCIMMaterializeSRAMPass());
  dump("sram-materialized");
  modulePassManager.addPass(createCIMExpandBitSerialPass());
  dump("bit-serial");
  CIMAllocateSRAMPassOptions sramOptions;
  sramOptions.reuse = sramAllocation == SRAMAllocation::Reuse;
  modulePassManager.addPass(createCIMAllocateSRAMPass(sramOptions));
  dump("sram-allocated");
  modulePassManager.addNestedPass<IREE::HAL::ExecutableOp>(
      createIREELowerAffinePass());
  modulePassManager.addNestedPass<IREE::HAL::ExecutableOp>(
      createCanonicalizerPass());
  dump("physical");
}

} // namespace mlir::iree_compiler::IREE::CIM
