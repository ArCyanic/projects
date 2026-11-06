#include "cim/Common/HardwareProfile.h"

#include "cim/Common/CIMExecutableFormat.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/IR/Attributes.h"

namespace mlir::iree_compiler::IREE::CIM {
ResolvedHardwareProfile getCompetitionHardwareProfile() {
  ResolvedHardwareProfile profile;
  profile.sramCapacityBytes = CIMX_COMPETITION_SRAM_CAPACITY_BYTES;
  profile.sramAlignmentBytes = 64;
  profile.arrayRows = CIMX_COMPETITION_ARRAY_ROWS;
  profile.arrayColumns = CIMX_COMPETITION_ARRAY_COLUMNS_BITS;
  return profile;
}

FailureOr<ResolvedHardwareProfile> resolveHardwareProfile(Operation *op) {
  auto target = IREE::HAL::ExecutableTargetAttr::lookup(op);
  auto config = target ? target.getConfiguration() : DictionaryAttr{};
  auto profile = config ? config.getAs<StringAttr>("profile") : StringAttr{};
  if (!profile)
    return op->emitOpError("missing CIM hardware profile in executable target"),
           failure();
  if (profile.getValue() != "competition") {
    op->emitOpError("unknown CIM hardware profile: ") << profile.getValue();
    return failure();
  }
  return getCompetitionHardwareProfile();
}

} // namespace mlir::iree_compiler::IREE::CIM
