#ifndef CIM_COMPILER_PLUGIN_CIM_TARGET_CIMCOMPILEROPTIONS_H_
#define CIM_COMPILER_PLUGIN_CIM_TARGET_CIMCOMPILEROPTIONS_H_

#include "cim/Common/CIMOptimizationPipeline.h"
#include "iree/compiler/Utils/OptionUtils.h"
#include <string>

namespace mlir::iree_compiler::IREE::CIM {

struct CIMOptions {
  std::string hardwareProfile = "competition";
  OptimizationPipeline optimizationPipeline = OptimizationPipeline::Replicated;
  SRAMAllocation sramAllocation = SRAMAllocation::Reuse;
  std::string dumpPhysicalizationTo;

  void bindOptions(OptionsBinder &binder);
};

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_TARGET_CIMCOMPILEROPTIONS_H_
