#include "cim/Target/CIMTargetBackend.h"

#include "cim/Codegen/CIMPasses.h"
#include "cim/Common/CIMExecutableFormat.h"
#include "cim/IR/CIMOps.h"
#include "cim/Target/CIMCompilerOptions.h"
#include "cim/Target/CIMExecutablePayload.h"
#include "iree/compiler/Codegen/Common/Passes.h"
#include "iree/compiler/Codegen/Dialect/Codegen/IR/IREECodegenDialect.h"
#include "iree/compiler/Dialect/HAL/IR/HALDialect.h"
#include "iree/compiler/Dialect/HAL/Target/TargetBackend.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"

namespace mlir::iree_compiler::IREE::CIM {
namespace {

IREE::HAL::ExecutableTargetAttr
getCIMExecutableTarget(MLIRContext *context, const CIMOptions &options) {
  Builder builder(context);
  return IREE::HAL::ExecutableTargetAttr::get(
      context, builder.getStringAttr("cim"),
      builder.getStringAttr(CIMX_EXECUTABLE_FORMAT),
      builder.getDictionaryAttr({builder.getNamedAttr(
          "profile", builder.getStringAttr(options.hardwareProfile))}));
}

} // namespace

CIMTargetBackend::CIMTargetBackend(const CIMOptions &options)
    : options(options) {}

std::string CIMTargetBackend::getLegacyDefaultDeviceID() const {
  return "local";
}

void CIMTargetBackend::getDefaultExecutableTargets(
    MLIRContext *context, StringRef deviceID, DictionaryAttr deviceConfigAttr,
    SmallVectorImpl<IREE::HAL::ExecutableTargetAttr> &targets) const {
  targets.push_back(getCIMExecutableTarget(context, options));
}

IREE::HAL::TargetBackend::SupportedTypes
CIMTargetBackend::getSupportedTypes(MLIRContext *context) const {
  SupportedTypes types;
  Builder builder(context);
  for (unsigned width : {8, 16, 32}) {
    Type type = builder.getIntegerType(width);
    types.addScalarType(type);
    types.addElementType(type);
  }
  return types;
}

void CIMTargetBackend::getDependentDialects(DialectRegistry &registry) const {
  registry.insert<CIMDialect, IREE::Codegen::IREECodegenDialect,
                  IREE::HAL::HALDialect, arith::ArithDialect,
                  memref::MemRefDialect>();
}

void CIMTargetBackend::buildConfigurationPassPipeline(
    IREE::HAL::ExecutableTargetAttr, OpPassManager &passManager) {
  buildCodegenConfigurationPreProcessingPassPipeline(passManager);
  buildCIMCodegenConfigurationPassPipeline(passManager.nest<ModuleOp>());
}

void CIMTargetBackend::buildTranslationPassPipeline(
    IREE::HAL::ExecutableTargetAttr, OpPassManager &passManager) {
  buildCIMCodegenTranslationPassPipeline(passManager.nest<ModuleOp>());
  buildCodegenTranslationPostProcessingPassPipeline(passManager);
}

void CIMTargetBackend::buildLinkingPassPipeline(OpPassManager &passManager) {
  buildCIMLinkingPassPipeline(passManager, options.optimizationPipeline,
                              options.sramAllocation,
                              options.dumpPhysicalizationTo);
}

LogicalResult CIMTargetBackend::serializeExecutable(
    const IREE::HAL::TargetBackend::SerializationOptions &options,
    IREE::HAL::ExecutableVariantOp variant, OpBuilder &builder) {
  auto artifacts = buildCIMExecutableArtifacts(variant);
  if (failed(artifacts))
    return failure();
  if (!options.dumpBinariesPath.empty()) {
    IREE::HAL::dumpDataToPath<uint8_t>(options.dumpBinariesPath,
                                       options.dumpBaseName, variant.getName(),
                                       ".cim.payload", artifacts->payload);
    IREE::HAL::dumpDataToPath(options.dumpBinariesPath, options.dumpBaseName,
                              variant.getName(), ".cim.isa", artifacts->isa);
  }
  auto binary = IREE::HAL::ExecutableBinaryOp::create(
      builder, variant.getLoc(), variant.getSymName(), CIMX_EXECUTABLE_FORMAT,
      std::move(artifacts->payload));
  binary.setMimeTypeAttr(
      builder.getStringAttr("application/vnd.cim.executable"));
  return success();
}

} // namespace mlir::iree_compiler::IREE::CIM
