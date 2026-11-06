#include "iree/compiler/Codegen/Utils/LinkingUtils.h"
#include "iree/compiler/Dialect/HAL/IR/HALDialect.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "iree/compiler/Utils/ModuleUtils.h"
#include "mlir/Pass/Pass.h"
#include "llvm/Support/FormatVariadic.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMLINKEXECUTABLESPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

constexpr llvm::StringLiteral kTarget = "cim";

LogicalResult linkExecutables(ModuleOp moduleOp, OpBuilder &moduleBuilder) {
  auto sources = gatherExecutablesForTarget(moduleOp, kTarget, false);
  auto lazySources = gatherExecutablesForTarget(moduleOp, kTarget, true);
  sources.append(lazySources);
  if (sources.empty())
    return success();
  if (sources.size() == 1) {
    sources.front().setLazy(false);
    return success();
  }

  SymbolTable moduleTable(moduleOp);
  std::string name =
      llvm::formatv("{0}_cim_linked", guessModuleName(moduleOp, "module"));
  auto linked =
      IREE::HAL::ExecutableOp::create(moduleBuilder, moduleOp.getLoc(), name);
  linked.setVisibility(sources.front().getVisibility());
  moduleTable.insert(linked);
  auto executableBuilder = OpBuilder::atBlockBegin(&linked.getBlock());

  auto targets = gatherExecutableTargets(sources);
  for (auto [index, target] : llvm::enumerate(targets)) {
    if (target.getBackend().getValue() != kTarget)
      continue;
    std::string variantName =
        targets.size() == 1
            ? target.getSymbolNameFragment()
            : llvm::formatv("{0}_{1}", target.getSymbolNameFragment(), index)
                  .str();
    auto variant = IREE::HAL::ExecutableVariantOp::create(
        executableBuilder, moduleOp.getLoc(), variantName, target);
    auto innerBuilder = OpBuilder::atBlockBegin(&variant.getBlock());
    ModuleOp::create(innerBuilder, moduleOp.getLoc());
    auto merge = [](ModuleOp source, ModuleOp destination,
                    DenseMap<StringRef, Operation *> &symbols) {
      return mergeModuleInto(source, destination, symbols);
    };
    if (failed(linkExecutablesInto(moduleOp, sources, linked, variant, merge)))
      return failure();
  }

  if (linked.getBody().empty())
    linked.erase();
  return success();
}

struct CIMLinkExecutablesPass final
    : impl::CIMLinkExecutablesPassBase<CIMLinkExecutablesPass> {
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<IREE::HAL::HALDialect>();
  }
  void runOnOperation() override {
    ModuleOp moduleOp = getOperation();
    OpBuilder builder = OpBuilder::atBlockBegin(moduleOp.getBody());
    if (failed(linkExecutables(moduleOp, builder)))
      signalPassFailure();
  }
};

} // namespace

} // namespace mlir::iree_compiler::IREE::CIM
