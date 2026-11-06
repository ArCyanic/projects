#include "cim/IR/CIMOps.h"

#include "mlir/IR/BuiltinAttributes.h"

namespace mlir::iree_compiler::IREE::CIM {

static bool compatibleDim(int64_t lhs, int64_t rhs) {
  return ShapedType::isDynamic(lhs) || ShapedType::isDynamic(rhs) || lhs == rhs;
}

LogicalResult ArrayLoadOp::verify() {
  auto srcType = cast<MemRefType>(getSrc().getType());
  auto dstType = cast<MemRefType>(getDst().getType());
  auto space = dyn_cast_or_null<MemorySpaceAttr>(dstType.getMemorySpace());
  if (srcType.getRank() != 2 || dstType.getRank() != 2 ||
      !compatibleDim(srcType.getDimSize(0), dstType.getDimSize(0)) ||
      !compatibleDim(srcType.getDimSize(1), dstType.getDimSize(1)) || !space ||
      space.getValue() != MemorySpace::Array)
    return emitOpError("requires matching rank-2 i8 source and Array view");
  return success();
}

LogicalResult MvmOp::verify() {
  auto srcType = cast<MemRefType>(getSrc().getType());
  auto weightType = cast<MemRefType>(getWeight().getType());
  auto dstType = cast<MemRefType>(getDst().getType());
  if (srcType.getRank() != 2 || weightType.getRank() != 2 ||
      dstType.getRank() != 2 || srcType.getDimSize(0) != 1 ||
      dstType.getDimSize(0) != 1 ||
      !compatibleDim(srcType.getDimSize(1), weightType.getDimSize(0)) ||
      !compatibleDim(weightType.getDimSize(1), dstType.getDimSize(1)))
    return emitOpError("requires [1,K] x [K,N] -> [1,N]");
  return success();
}

LogicalResult EltOp::verify() {
  bool vv = getMode() == EltMode::VV;
  if (vv != static_cast<bool>(getSrc2()) ||
      vv == static_cast<bool>(getImmediateAttr()))
    return emitOpError("requires vv src2 or vi immediate");
  auto srcType = cast<MemRefType>(getSrc1().getType());
  auto dstType = cast<MemRefType>(getDst().getType());
  if (srcType.getRank() != 1 || dstType.getRank() != 1 ||
      srcType.getElementType() != dstType.getElementType() ||
      !compatibleDim(srcType.getDimSize(0), dstType.getDimSize(0)))
    return emitOpError("requires equal rank-1 buffers");
  if (vv) {
    auto src2Type = cast<MemRefType>(getSrc2().getType());
    if (src2Type.getRank() != 1 ||
        src2Type.getElementType() != dstType.getElementType() ||
        !compatibleDim(src2Type.getDimSize(0), dstType.getDimSize(0)))
      return emitOpError("requires an equal rank-1 vv source");
  }
  return success();
}

} // namespace mlir::iree_compiler::IREE::CIM

#define GET_OP_CLASSES
#include "cim/IR/CIMOps.cpp.inc"
