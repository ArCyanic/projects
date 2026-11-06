#ifndef CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMMVMUTILS_H_
#define CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMMVMUTILS_H_

#include "cim/Codegen/StaticArrayPlacement.h"
#include "cim/IR/CIMOps.h"
#include "mlir/Analysis/AliasAnalysis.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/IR/SymbolTable.h"
#include "llvm/ADT/STLFunctionalExtras.h"

namespace mlir::linalg {
class LinalgOp;
}

namespace mlir::iree_compiler::IREE::CIM {

bool isSignedContraction(linalg::LinalgOp op);
bool mayAlias(Value lhs, Value rhs, AliasAnalysis &analysis);
ModRefResult memoryAccess(Operation *op, Value target, AliasAnalysis &analysis);
bool canFuseMVMs(MvmOp first, MvmOp next, AliasAnalysis &analysis);

FailureOr<SmallVector<int8_t>> readI8Elements(ElementsAttr elements);
/// Resolves the storage root and reports byte-offset terms along the view
/// chain. Reinterpret casts replace strided offsets while byte views shift the
/// aligned base pointer.
FailureOr<Value> resolveBufferBase(
    Value value,
    llvm::function_ref<LogicalResult(OpFoldResult, int64_t)> accumulate);
FailureOr<DenseWeight> readDenseWeight(Value value);
memref::GlobalOp createDenseWeight(ModuleOp module, SymbolTable &symbols,
                                   ArrayRef<int8_t> data, int64_t k, int64_t n,
                                   StringRef name = "__cim_weight");
Value packMVMRows(OpBuilder &builder, Value first, int64_t count, int64_t k);
bool areConsecutiveMVMRows(MvmOp previous, MvmOp next);
Value packMVMColumns(OpBuilder &builder, Value first, int64_t columns);
bool areConsecutiveMVMColumns(MvmOp previous, MvmOp next);
/// Rank-reduces a `[1,N]` accumulator view to the rank-1 `[N]` form `cim.elt`
/// requires. Fails on any other shape.
FailureOr<Value> flatMVMResult(OpBuilder &builder, Location loc, Value value);

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_CODEGEN_CIMMVMUTILS_H_
