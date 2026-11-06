#include "cim/Target/CIMCompilerOptions.h"

#include "llvm/Support/CommandLine.h"

namespace mlir::iree_compiler::IREE::CIM {

void CIMOptions::bindOptions(OptionsBinder &binder) {
  static llvm::cl::OptionCategory category("IREE CIM Plugin");
  binder.opt<std::string>(
      "iree-cim-hardware-profile", hardwareProfile,
      llvm::cl::desc("Built-in hardware profile name: competition"),
      llvm::cl::cat(category));
  binder.opt<OptimizationPipeline>(
      "iree-cim-optimization-pipeline", optimizationPipeline,
      llvm::cl::desc("Fixed CIM optimization pipeline"),
      llvm::cl::cat(category),
      llvm::cl::values(clEnumValN(OptimizationPipeline::Direct, "direct",
                                  "Sequential SRAM baseline"),
                       clEnumValN(OptimizationPipeline::Packed, "packed",
                                  "Pack MVMs sharing an activation"),
                       clEnumValN(OptimizationPipeline::Heterogeneous,
                                  "heterogeneous",
                                  "Fuse heterogeneous block-diagonal MVMs"),
                       clEnumValN(OptimizationPipeline::Replicated,
                                  "replicated", "Pack and replicate MVMs")));
  binder.opt<SRAMAllocation>(
      "iree-cim-sram-allocation", sramAllocation,
      llvm::cl::desc("CIM SRAM allocation strategy"), llvm::cl::cat(category),
      llvm::cl::values(clEnumValN(SRAMAllocation::Sequential, "sequential",
                                  "Place buffers sequentially"),
                       clEnumValN(SRAMAllocation::Reuse, "reuse",
                                  "Reuse non-overlapping lifetimes")));
  binder.opt<std::string>(
      "iree-cim-dump-physicalization-to", dumpPhysicalizationTo,
      llvm::cl::desc("Directory receiving one MLIR file per CIM "
                     "physicalization stage"),
      llvm::cl::cat(category));
}

} // namespace mlir::iree_compiler::IREE::CIM

IREE_DEFINE_COMPILER_OPTION_FLAGS(mlir::iree_compiler::IREE::CIM::CIMOptions);
