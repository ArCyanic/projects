#include "cim/Codegen/CIMPasses.h"

#include "cim/Codegen/CIMMVMUtils.h"
#include "cim/IR/CIMDialect.h"
#include "cim/IR/CIMOps.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/Pass/Pass.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMEXPANDBITSERIALPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

/// Rewrites one `cim.mvm` into the bit-serial rounds the Array actually
/// executes:
///
///   dst = bit_0
///   dst = dst + 2^i * bit_i     for 0 < i < B-1
///   dst = dst - 2^(B-1) * bit_(B-1)
///
/// which reconstructs the signed product because a two's-complement activation
/// is `-2^(B-1)*s_(B-1) + sum_(i<B-1) 2^i*s_i`.
static void expand(MvmOp mvm) {
  OpBuilder builder(mvm);
  Location loc = mvm.getLoc();
  Value src = mvm.getSrc(), weight = mvm.getWeight(), dst = mvm.getDst();
  unsigned bits = cast<MemRefType>(src.getType()).getElementTypeBitWidth();

  BitOp::create(builder, loc, src, weight, dst, 0);

  auto dstType = cast<MemRefType>(dst.getType());
  auto scratchType =
      MemRefType::get(dstType.getShape(), dstType.getElementType());
  Value scratch = memref::AllocOp::create(builder, loc, scratchType);
  Value dstFlat = *flatMVMResult(builder, loc, dst);
  Value scratchFlat = *flatMVMResult(builder, loc, scratch);
  for (unsigned index = 1; index < bits; ++index) {
    BitOp::create(builder, loc, src, weight, scratch, index);
    EltOp::create(builder, loc, scratchFlat, Value(), scratchFlat,
                  EltOpcode::Mul, EltMode::VI,
                  builder.getI64IntegerAttr(int64_t{1} << index));
    EltOp::create(builder, loc, dstFlat, scratchFlat, dstFlat,
                  index + 1 == bits ? EltOpcode::Sub : EltOpcode::Add,
                  EltMode::VV, IntegerAttr{});
  }
  mvm.erase();
}

struct CIMExpandBitSerialPass final
    : impl::CIMExpandBitSerialPassBase<CIMExpandBitSerialPass> {
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<memref::MemRefDialect, CIMDialect>();
  }

  void runOnOperation() override {
    for (auto variant : cimVariants(getOperation())) {
      SmallVector<MvmOp> mvms;
      variant.getInnerModule().walk([&](MvmOp op) { mvms.push_back(op); });
      for (MvmOp mvm : mvms)
        expand(mvm);
    }
  }
};

} // namespace
} // namespace mlir::iree_compiler::IREE::CIM
