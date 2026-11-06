#ifndef CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMPASSES_H_
#define CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMPASSES_H_

#include "cim/Common/CIMOptimizationPipeline.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/Pass/PassManager.h"
#include "llvm/ADT/SmallVector.h"
#include "llvm/ADT/StringRef.h"
#include <memory>

namespace mlir::iree_compiler::IREE::CIM {

SmallVector<IREE::HAL::ExecutableVariantOp> cimVariants(ModuleOp module);
void buildCIMCodegenConfigurationPassPipeline(OpPassManager &modulePassManager);
void buildCIMCodegenTranslationPassPipeline(OpPassManager &modulePassManager);
void buildCIMLinkingPassPipeline(OpPassManager &modulePassManager,
                                 OptimizationPipeline pipeline,
                                 SRAMAllocation sramAllocation,
                                 StringRef dumpPhysicalizationTo);
std::unique_ptr<Pass> createCIMFuseHeterogeneousContractionsPass();
void registerCIMCodegenPasses();

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMPASSES_H_
