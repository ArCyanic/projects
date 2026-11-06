#ifndef CIM_COMPILER_PLUGIN_CIM_FRONTEND_CIMNORMALIZEONNXLINEAR_H_
#define CIM_COMPILER_PLUGIN_CIM_FRONTEND_CIMNORMALIZEONNXLINEAR_H_

#include "mlir/Pass/Pass.h"

#include <memory>

namespace mlir::iree_compiler::IREE::CIM {

std::unique_ptr<Pass> createCIMNormalizeONNXLinearPass();
void registerCIMFrontendPasses();

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_FRONTEND_CIMNORMALIZEONNXLINEAR_H_
