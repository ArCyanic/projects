#ifndef CIM_COMPILER_PLUGIN_CIM_TARGET_CIMEXECUTABLEPAYLOAD_H_
#define CIM_COMPILER_PLUGIN_CIM_TARGET_CIMEXECUTABLEPAYLOAD_H_

#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include <string>
#include <vector>

namespace mlir::iree_compiler::IREE::CIM {

struct CIMExecutableArtifacts {
  std::vector<uint8_t> payload;
  std::string isa;
};
FailureOr<CIMExecutableArtifacts>
buildCIMExecutableArtifacts(IREE::HAL::ExecutableVariantOp variant);

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_TARGET_CIMEXECUTABLEPAYLOAD_H_
