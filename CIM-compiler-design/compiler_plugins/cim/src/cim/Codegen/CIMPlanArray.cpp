#include "cim/Codegen/CIMArrayInitialization.h"
#include "cim/Codegen/CIMMVMUtils.h"
#include "cim/Codegen/CIMPasses.h"
#include "cim/Codegen/StaticArrayPlacement.h"
#include "cim/Common/HardwareProfile.h"
#include "cim/IR/CIMOps.h"
#include "iree/compiler/Dialect/HAL/IR/HALDialect.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/IR/SymbolTable.h"
#include "mlir/Pass/Pass.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMPLANARRAYPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

static Value arrayView(OpBuilder &builder, Location loc, memref::GlobalOp array,
                       const StaticArrayRegion &region) {
  return memref::SubViewOp::create(
      builder, loc,
      memref::GetGlobalOp::create(builder, loc, array.getType(),
                                  array.getNameAttr()),
      ArrayRef<int64_t>{region.row, region.column},
      ArrayRef<int64_t>{region.rows, region.columns}, ArrayRef<int64_t>{1, 1});
}

static IREE::HAL::ExecutableExportOp
createInit(IREE::HAL::ExecutableVariantOp variant, ModuleOp module,
           SymbolTable &symbols, memref::GlobalOp array,
           const StaticArrayPlan &plan) {
  OpBuilder moduleBuilder = OpBuilder::atBlockBegin(module.getBody());
  auto init =
      func::FuncOp::create(moduleBuilder, module.getLoc(), "__cim_array_init",
                           moduleBuilder.getFunctionType({}, {}));
  init.setPublic();
  symbols.insert(init);
  Block *entry = init.addEntryBlock();
  OpBuilder builder = OpBuilder::atBlockBegin(entry);
  for (const StaticArrayRegion &region : plan.regions) {
    auto weight = createDenseWeight(module, symbols, region.data, region.rows,
                                    region.columns, "__cim_weight");
    ArrayLoadOp::create(builder, module.getLoc(),
                        memref::GetGlobalOp::create(builder, module.getLoc(),
                                                    weight.getType(),
                                                    weight.getNameAttr()),
                        arrayView(builder, module.getLoc(), array, region));
  }
  func::ReturnOp::create(builder, module.getLoc());

  int64_t ordinal = 0;
  for (auto exportOp : variant.getExportOps())
    ordinal =
        std::max<int64_t>(ordinal, exportOp.getOrdinal()->getSExtValue() + 1);
  OpBuilder variantBuilder = OpBuilder::atBlockBegin(&variant.getBlock());
  auto layout = IREE::HAL::PipelineLayoutAttr::get(
      module.getContext(), {}, 0, IREE::HAL::PipelineLayoutFlags::None);
  return IREE::HAL::ExecutableExportOp::create(
      variantBuilder, module.getLoc(), init.getNameAttr(),
      variantBuilder.getIndexAttr(ordinal), layout, ArrayAttr{}, IntegerAttr{},
      IntegerAttr{});
}

static LogicalResult planVariant(IREE::HAL::ExecutableVariantOp variant) {
  auto profile = resolveHardwareProfile(variant);
  if (failed(profile))
    return failure();
  int64_t arrayColumns = profile->arrayCellColumns();
  ModuleOp module = variant.getInnerModule();
  SymbolTable symbols(module);

  SmallVector<MvmOp> mvms;
  module.walk([&](MvmOp op) { mvms.push_back(op); });
  SmallVector<DenseWeight> weights;
  weights.reserve(mvms.size());
  for (MvmOp op : mvms) {
    auto weight = readDenseWeight(op.getWeight());
    if (failed(weight))
      return failure();
    weights.push_back(std::move(*weight));
  }
  auto inventory = llvm::map_to_vector(
      weights, [](const DenseWeight &weight) { return &weight; });
  auto plan = planStaticArray(inventory, profile->arrayRows, arrayColumns);
  if (!plan)
    return variant.emitError(llvm::toString(plan.takeError()));

  OpBuilder detached(module.getContext());
  auto arrayType = MemRefType::get(
      {profile->arrayRows, arrayColumns}, detached.getI8Type(), AffineMap(),
      MemorySpaceAttr::get(module.getContext(), MemorySpace::Array));
  auto array =
      memref::GlobalOp::create(detached, module.getLoc(), "__cim_array",
                               detached.getStringAttr("private"), arrayType,
                               ElementsAttr(), false, IntegerAttr());
  symbols.insert(array);
  auto initExport = createInit(variant, module, symbols, array, *plan);

  for (auto [op, use] : llvm::zip_equal(mvms, plan->uses)) {
    OpBuilder builder(op);
    for (const StaticArraySlice &slice : use) {
      const StaticArrayRegion &region = plan->regions[slice.region];
      Value physical = arrayView(builder, op.getLoc(), array, region);
      if (use.size() == 1) {
        op.getWeightMutable().assign(physical);
        continue;
      }
      Value destination = memref::SubViewOp::create(
          builder, op.getLoc(), op.getDst(),
          ArrayRef<int64_t>{0, slice.nOffset},
          ArrayRef<int64_t>{1, region.columns}, ArrayRef<int64_t>{1, 1});
      MvmOp::create(builder, op.getLoc(), op.getSrc(), physical, destination);
    }
    if (use.size() != 1)
      op.erase();
  }
  return materializeArrayInitialization(initExport);
}

struct CIMPlanArrayPass final : impl::CIMPlanArrayPassBase<CIMPlanArrayPass> {
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<IREE::CIM::CIMDialect, IREE::HAL::HALDialect,
                    func::FuncDialect, memref::MemRefDialect>();
  }

  void runOnOperation() override {
    auto variants = cimVariants(getOperation());
    if (variants.size() != 1) {
      getOperation().emitError("expected exactly one linked CIM variant");
      return signalPassFailure();
    }
    if (failed(planVariant(variants.front())))
      signalPassFailure();
  }
};

} // namespace
} // namespace mlir::iree_compiler::IREE::CIM
