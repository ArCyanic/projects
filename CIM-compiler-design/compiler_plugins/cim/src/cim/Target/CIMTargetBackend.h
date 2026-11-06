#ifndef CIM_COMPILER_PLUGIN_CIM_TARGET_CIMTARGETBACKEND_H_
#define CIM_COMPILER_PLUGIN_CIM_TARGET_CIMTARGETBACKEND_H_

#include "iree/compiler/Dialect/HAL/Target/TargetBackend.h"

namespace mlir::iree_compiler::IREE::CIM {

struct CIMOptions;

class CIMTargetBackend final : public IREE::HAL::TargetBackend {
public:
  explicit CIMTargetBackend(const CIMOptions &options);

  std::string getLegacyDefaultDeviceID() const final;

  void getDefaultExecutableTargets(
      MLIRContext *context, StringRef deviceID, DictionaryAttr deviceConfigAttr,
      SmallVectorImpl<IREE::HAL::ExecutableTargetAttr> &executableTargetAttrs)
      const final;

  IREE::HAL::TargetBackend::SupportedTypes
  getSupportedTypes(MLIRContext *context) const final;

  void getDependentDialects(DialectRegistry &registry) const final;

  void
  buildConfigurationPassPipeline(IREE::HAL::ExecutableTargetAttr targetAttr,
                                 OpPassManager &passManager) final;

  void buildTranslationPassPipeline(IREE::HAL::ExecutableTargetAttr targetAttr,
                                    OpPassManager &passManager) final;

  void buildLinkingPassPipeline(OpPassManager &passManager) final;

  LogicalResult serializeExecutable(
      const IREE::HAL::TargetBackend::SerializationOptions &options,
      IREE::HAL::ExecutableVariantOp variantOp,
      OpBuilder &executableBuilder) final;

private:
  const CIMOptions &options;
};

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_TARGET_CIMTARGETBACKEND_H_
