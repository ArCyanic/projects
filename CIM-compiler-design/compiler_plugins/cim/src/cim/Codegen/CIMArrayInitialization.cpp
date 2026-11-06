#include "cim/Codegen/CIMArrayInitialization.h"

#include "iree/compiler/Dialect/HAL/Analysis/DeviceAnalysis.h"
#include "iree/compiler/Dialect/Util/IR/UtilOps.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Interfaces/FunctionInterfaces.h"
#include "llvm/ADT/SetVector.h"

namespace mlir::iree_compiler::IREE::CIM {

LogicalResult
materializeArrayInitialization(IREE::HAL::ExecutableExportOp initExport) {
  auto variant = initExport->getParentOfType<IREE::HAL::ExecutableVariantOp>();
  auto executable = variant->getParentOfType<IREE::HAL::ExecutableOp>();
  auto module = executable->getParentOfType<ModuleOp>();

  IREE::HAL::DeviceAnalysis deviceAnalysis(module);
  if (failed(deviceAnalysis.run())) {
    return initExport.emitOpError("failed to analyze the host device owner");
  }
  llvm::SetVector<IREE::Util::GlobalOpInterface> deviceGlobals;
  auto executableRef = FlatSymbolRefAttr::get(executable);
  WalkResult walkResult =
      module.walk([&](IREE::HAL::ExecutableLookupOp lookup) {
        if (lookup.getExecutableAttr() != executableRef) {
          return WalkResult::advance();
        }
        auto globals = deviceAnalysis.lookupDeviceGlobals(lookup.getDevice());
        if (!globals || globals->size() != 1) {
          lookup.emitOpError("expected one device owner");
          return WalkResult::interrupt();
        }
        deviceGlobals.insert(globals->front());
        return WalkResult::advance();
      });
  if (walkResult.wasInterrupted()) {
    return failure();
  }
  if (deviceGlobals.size() != 1) {
    return executable.emitOpError(
        "expected all host lookups to share one device owner");
  }

  Location loc = initExport.getLoc();
  OpBuilder moduleBuilder = OpBuilder::atBlockEnd(module.getBody());
  auto initializer = IREE::Util::InitializerOp::create(moduleBuilder, loc);
  OpBuilder builder = OpBuilder::atBlockBegin(initializer.addEntryBlock());
  auto deviceGlobal = deviceGlobals.front();
  Value device = deviceGlobal.createLoadOp(loc, builder).getLoadedGlobalValue();
  Value affinity = arith::ConstantIntOp::create(builder, loc, -1, 64);
  auto modes = IREE::HAL::CommandBufferModeBitfield::OneShot |
               IREE::HAL::CommandBufferModeBitfield::AllowInlineExecution;
  Value commandBuffer =
      IREE::HAL::CommandBufferCreateOp::create(
          builder, loc, builder.getType<IREE::HAL::CommandBufferType>(), device,
          modes, IREE::HAL::CommandCategoryBitfield::Dispatch, affinity,
          Value{})
          .getResult();
  auto exportRef = SymbolRefAttr::get(
      executable.getNameAttr(),
      {FlatSymbolRefAttr::get(variant), FlatSymbolRefAttr::get(initExport)});
  Value executableValue = IREE::HAL::ExecutableLookupOp::create(
      builder, loc, builder.getType<IREE::HAL::ExecutableType>(), device,
      executable.getName());
  Value functionId = IREE::HAL::ExecutableLookupFunctionOp::create(
      builder, loc, builder.getI64Type(), executableValue, exportRef);
  Value one = arith::ConstantIndexOp::create(builder, loc, 1);
  IREE::HAL::CommandBufferDispatchOp::create(
      builder, loc, commandBuffer, executableValue, functionId,
      ValueRange{one, one, one}, ValueRange{},
      ArrayRef<IREE::HAL::BindingValue>{}, IREE::HAL::DispatchFlags::None);
  IREE::HAL::CommandBufferFinalizeOp::create(builder, loc, commandBuffer);

  Value waitFence = IREE::Util::NullOp::create(
      builder, loc, builder.getType<IREE::HAL::FenceType>());
  Value signalFence = IREE::HAL::FenceCreateOp::create(
      builder, loc, builder.getType<IREE::HAL::FenceType>(), device,
      IREE::HAL::FenceFlagBitfield::None);
  IREE::HAL::DeviceQueueExecuteOp::create(builder, loc, device, affinity,
                                          waitFence, signalFence, commandBuffer,
                                          IREE::HAL::ExecuteFlagBitfield::None);
  Value timeout = arith::ConstantIntOp::create(builder, loc, -1, 32);
  auto await = IREE::HAL::FenceAwaitOp::create(
      builder, loc, builder.getI32Type(), timeout,
      IREE::HAL::WaitFlagBitfield::None, signalFence);
  IREE::Util::StatusCheckOkOp::create(builder, loc, await.getStatus(),
                                      "CIM Array initialization failed");
  IREE::Util::ReturnOp::create(builder, loc);
  return success();
}

} // namespace mlir::iree_compiler::IREE::CIM
