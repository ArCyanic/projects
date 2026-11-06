#ifndef CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMARRAYINITIALIZATION_H_
#define CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMARRAYINITIALIZATION_H_

#include "iree/compiler/Dialect/HAL/IR/HALOps.h"

namespace mlir::iree_compiler::IREE::CIM {

LogicalResult
materializeArrayInitialization(IREE::HAL::ExecutableExportOp initExport);

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMARRAYINITIALIZATION_H_
