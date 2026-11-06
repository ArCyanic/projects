#ifndef CIM_COMPILER_PLUGIN_CIM_COMMON_CIMOPTIMIZATIONPIPELINE_H_
#define CIM_COMPILER_PLUGIN_CIM_COMMON_CIMOPTIMIZATIONPIPELINE_H_

namespace mlir::iree_compiler::IREE::CIM {

enum class OptimizationPipeline { Direct, Packed, Heterogeneous, Replicated };

enum class SRAMAllocation { Sequential, Reuse };

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_COMMON_CIMOPTIMIZATIONPIPELINE_H_
