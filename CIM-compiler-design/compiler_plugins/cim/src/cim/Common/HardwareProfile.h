#ifndef CIM_COMPILER_PLUGIN_CIM_COMMON_HARDWAREPROFILE_H_
#define CIM_COMPILER_PLUGIN_CIM_COMMON_HARDWAREPROFILE_H_

#include "mlir/Support/LogicalResult.h"
#include <cstdint>

namespace mlir {
class Operation;
} // namespace mlir

namespace mlir::iree_compiler::IREE::CIM {

struct ResolvedHardwareProfile {
  uint32_t sramCapacityBytes = 0;
  uint32_t sramAlignmentBytes = 64;
  uint32_t arrayRows = 0;
  uint32_t arrayColumns = 0;

  /// Array columns counted in i8 cells rather than physical bits. Weight
  /// placement, tiling and the ISA all address the Array in cells.
  uint32_t arrayCellColumns() const { return arrayColumns / 8; }
};

ResolvedHardwareProfile getCompetitionHardwareProfile();

/// Resolves the enclosing target's profile and diagnoses invalid configuration
/// on the operation that needs it.
FailureOr<ResolvedHardwareProfile> resolveHardwareProfile(Operation *op);

} // namespace mlir::iree_compiler::IREE::CIM

#endif // CIM_COMPILER_PLUGIN_CIM_COMMON_HARDWAREPROFILE_H_
