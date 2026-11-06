#include "cim/Codegen/CIMPasses.h"

#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/Pass/Pass.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/raw_ostream.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DECL_CIMDUMPPHYSICALIZATIONPASS
#define GEN_PASS_DEF_CIMDUMPPHYSICALIZATIONPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

/// Writes the CIM target variants to `<path>/<label>.mlir` so each
/// physicalization stage leaves an inspectable intermediate result. Only the
/// CIM variants are written: the surrounding host HAL module is unchanged by
/// these passes and would bury the target program.
struct CIMDumpPhysicalizationPass final
    : impl::CIMDumpPhysicalizationPassBase<CIMDumpPhysicalizationPass> {
  using Base::Base;

  void runOnOperation() override {
    std::error_code ec = llvm::sys::fs::create_directories(path);
    llvm::raw_fd_ostream os(path + "/" + label + ".mlir", ec);
    if (ec) {
      getOperation().emitError()
          << "cannot write CIM stage dump to " << path << ": " << ec.message();
      return signalPassFailure();
    }
    for (auto variant : cimVariants(getOperation()))
      variant.print(os);
  }
};

} // namespace
} // namespace mlir::iree_compiler::IREE::CIM
