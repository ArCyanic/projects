# One compiler plugin; source directories remain the code organization.
iree_tablegen_library(
  NAME CIMOpsGen
  TD_FILE "src/cim/IR/CIMOps.td"
  OUTS
    --gen-dialect-decls --dialect=cim src/cim/IR/CIMDialect.h.inc
    --gen-dialect-defs --dialect=cim src/cim/IR/CIMDialect.cpp.inc
    --gen-enum-decls --dialect=cim src/cim/IR/CIMEnums.h.inc
    --gen-enum-defs --dialect=cim src/cim/IR/CIMEnums.cpp.inc
    --gen-attrdef-decls --attrdefs-dialect=cim src/cim/IR/CIMAttrs.h.inc
    --gen-attrdef-defs --attrdefs-dialect=cim src/cim/IR/CIMAttrs.cpp.inc
    --gen-op-decls --dialect=cim src/cim/IR/CIMOps.h.inc
    --gen-op-defs --dialect=cim src/cim/IR/CIMOps.cpp.inc
)

iree_tablegen_library(
  NAME CIMPassesGen
  TD_FILE "src/cim/Codegen/CIMPasses.td"
  OUTS
    --gen-pass-decls src/cim/Codegen/CIMPasses.h.inc
)

iree_cc_library(
  NAME registration
  SRCS
    "src/PluginRegistration.cpp"
    "src/cim/Codegen/CIMAllocateSRAM.cpp"
    "src/cim/Codegen/CIMArrayInitialization.cpp"
    "src/cim/Codegen/CIMDumpPhysicalization.cpp"
    "src/cim/Codegen/CIMExpandBitSerial.cpp"
    "src/cim/Codegen/CIMFuseHeterogeneousContractions.cpp"
    "src/cim/Codegen/CIMLegalizeArrayTiles.cpp"
    "src/cim/Codegen/CIMLinkExecutables.cpp"
    "src/cim/Codegen/CIMLowerExecutableTargetPass.cpp"
    "src/cim/Codegen/CIMMVMUtils.cpp"
    "src/cim/Codegen/CIMMaterializeSRAM.cpp"
    "src/cim/Codegen/CIMOptimizeMVM.cpp"
    "src/cim/Codegen/CIMPasses.cpp"
    "src/cim/Codegen/CIMPlanArray.cpp"
    "src/cim/Codegen/CIMSelectLoweringStrategyPass.cpp"
    "src/cim/Codegen/Conversion/CIMToTarget.cpp"
    "src/cim/Codegen/Conversion/LinalgToCIM.cpp"
    "src/cim/Codegen/StaticArrayPlacement.cpp"
    "src/cim/Common/HardwareProfile.cpp"
    "src/cim/Frontend/CIMNormalizeONNXLinear.cpp"
    "src/cim/IR/CIMDialect.cpp"
    "src/cim/IR/CIMOps.cpp"
    "src/cim/Target/CIMCompilerOptions.cpp"
    "src/cim/Target/CIMExecutablePayload.cpp"
    "src/cim/Target/CIMTargetBackend.cpp"
  INCLUDES
    "${CMAKE_CURRENT_SOURCE_DIR}/src"
    "${CMAKE_CURRENT_BINARY_DIR}/src"
  DEPS
    ::CIMOpsGen
    ::CIMPassesGen
    LLVMSupport
    MLIRAffineDialect
    MLIRAnalysis
    MLIRArithDialect
    MLIRBufferizationDialect
    MLIRBufferizationTransforms
    MLIRFuncDialect
    MLIRFunctionInterfaces
    MLIRIR
    MLIRLinalgDialect
    MLIRLinalgInterfacesIncGenLib
    MLIRLinalgTransforms
    MLIRMemRefDialect
    MLIRPass
    MLIRSCFDialect
    MLIRSCFTransforms
    MLIRSCFUtils
    MLIRSideEffectInterfaces
    MLIRSupport
    MLIRTensorDialect
    MLIRTransforms
    MLIRValueBoundsOpInterface
    MLIRViewLikeInterface
    iree::compiler::Codegen::Common
    iree::compiler::Codegen::Common::GPU::CommonGPUPasses
    iree::compiler::Codegen::Dialect::Codegen::IR::IREECodegenDialect
    iree::compiler::Codegen::Utils
    iree::compiler::Dialect::HAL::Analysis
    iree::compiler::Dialect::HAL::IR
    iree::compiler::Dialect::HAL::Target
    iree::compiler::Dialect::LinalgExt::Utils
    iree::compiler::Dialect::TensorExt::IR
    iree::compiler::Dialect::Util::Analysis
    iree::compiler::Dialect::Util::IR
    iree::compiler::Dialect::Util::Transforms
    iree::compiler::DispatchCreation
    iree::compiler::PluginAPI
    iree::compiler::Transforms
    iree::compiler::Utils
    iree::compiler::plugins::input::Torch::torch-mlir::TorchConversionDialectIR
    iree::compiler::plugins::input::Torch::torch-mlir::TorchDialectIR
  PUBLIC
)

iree_compiler_register_plugin(PLUGIN_ID cim TARGET ::registration)
