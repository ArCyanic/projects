#ifndef CIM_CODEGEN_PASSES
#define CIM_CODEGEN_PASSES

include "mlir/Pass/PassBase.td"

def CIMSelectLoweringStrategyPass :
    Pass<"cim-select-lowering-strategy", "mlir::ModuleOp">;
def CIMLowerExecutableTargetPass : InterfacePass<
    "cim-lower-executable-target", "mlir::FunctionOpInterface">;
def CIMLegalizeArrayTilesPass :
    InterfacePass<"cim-legalize-array-tiles", "mlir::FunctionOpInterface">;
def CIMConvertLinalgToCIMPass :
    InterfacePass<"cim-convert-linalg-to-cim", "mlir::FunctionOpInterface">;
def CIMConvertToTargetIRPass :
    Pass<"cim-convert-to-target-ir", "mlir::ModuleOp">;
def CIMLinkExecutablesPass :
    Pass<"cim-link-executables", "mlir::ModuleOp">;
def CIMFuseHeterogeneousContractionsPass :
    Pass<"cim-fuse-heterogeneous-contractions", "mlir::ModuleOp">;
def CIMPackHorizontalMVMsPass :
    Pass<"cim-pack-horizontal-mvms", "mlir::ModuleOp">;
def CIMReplicateWeightMVMsPass :
    Pass<"cim-replicate-weight-mvms", "mlir::ModuleOp">;
def CIMPlanArrayPass : Pass<"cim-plan-array", "mlir::ModuleOp">;
def CIMMaterializeSRAMPass :
    Pass<"cim-materialize-sram", "mlir::ModuleOp">;
def CIMExpandBitSerialPass :
    Pass<"cim-expand-bit-serial", "mlir::ModuleOp">;
def CIMAllocateSRAMPass : Pass<"cim-allocate-sram", "mlir::ModuleOp"> {
  let options = [
    Option<"reuse", "reuse", "bool", "true",
           "Reuse storage across non-overlapping lifetimes">,
  ];
}
def CIMDumpPhysicalizationPass :
    Pass<"cim-dump-physicalization", "mlir::ModuleOp"> {
  let options = [
    Option<"path", "path", "std::string", [{""}],
           "Directory receiving the stage dump">,
    Option<"label", "label", "std::string", [{""}],
           "Stage name used as the dump file name">,
  ];
}

#endif // CIM_CODEGEN_PASSES
