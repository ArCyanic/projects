#include "cim/Common/HardwareProfile.h"
#include "cim/IR/CIMDialect.h"
#include "cim/IR/CIMOps.h"
#include "iree/compiler/Codegen/Dialect/Codegen/IR/IREECodegenOps.h"
#include "iree/compiler/Codegen/Utils/Utils.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/Dialect/Affine/IR/AffineOps.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Bufferization/Transforms/BufferUtils.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/Linalg/IR/Linalg.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/Dialect/SCF/IR/SCF.h"
#include "mlir/IR/BuiltinDialect.h"
#include "mlir/IR/Matchers.h"
#include "mlir/IR/SymbolTable.h"
#include "mlir/Interfaces/ValueBoundsOpInterface.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Transforms/DialectConversion.h"
namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMCONVERTTOTARGETIRPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {

struct ConvertZeroFill final : OpConversionPattern<linalg::FillOp> {
  ConvertZeroFill(MLIRContext *context, SymbolTableCollection &symbols)
      : OpConversionPattern(context), symbols(symbols) {}

  LogicalResult
  matchAndRewrite(linalg::FillOp op, OpAdaptor adaptor,
                  ConversionPatternRewriter &rewriter) const override {
    if (!op.hasPureBufferSemantics() ||
        !matchPattern(adaptor.getInputs().front(), m_Zero()))
      return failure();
    Value target = adaptor.getOutputs().front();
    auto targetType = cast<MemRefType>(target.getType());
    SmallVector<int64_t> shape;
    for (unsigned dim = 0; dim < targetType.getRank(); ++dim) {
      int64_t size = targetType.getDimSize(dim);
      if (ShapedType::isDynamic(size)) {
        auto bound = ValueBoundsConstraintSet::computeConstantBound(
            presburger::BoundType::UB, {target, dim}, nullptr,
            ValueBoundsOptions{/*closedUB=*/true});
        if (failed(bound))
          return failure();
        size = *bound;
      }
      shape.push_back(size);
    }

    auto tensorType = RankedTensorType::get(shape, targetType.getElementType());
    auto constant = arith::ConstantOp::create(
        rewriter, op.getLoc(),
        DenseElementsAttr::get(
            tensorType, rewriter.getZeroAttr(targetType.getElementType())));
    auto global = bufferization::getGlobalFor(constant, symbols, 0);
    rewriter.eraseOp(constant);
    if (failed(global))
      return failure();
    Value source = memref::GetGlobalOp::create(
        rewriter, op.getLoc(), global->getType(), global->getNameAttr());
    if (!targetType.hasStaticShape()) {
      SmallVector<OpFoldResult> offsets(targetType.getRank(),
                                        rewriter.getIndexAttr(0));
      auto sizes = memref::getMixedSizes(rewriter, op.getLoc(), target);
      SmallVector<OpFoldResult> strides(targetType.getRank(),
                                        rewriter.getIndexAttr(1));
      source = memref::SubViewOp::create(rewriter, op.getLoc(), source, offsets,
                                         sizes, strides);
    }
    memref::CopyOp::create(rewriter, op.getLoc(), source, target);
    rewriter.eraseOp(op);
    return success();
  }

  SymbolTableCollection &symbols;
};

struct ConvertWorkgroupSize final
    : OpConversionPattern<IREE::HAL::InterfaceWorkgroupSizeOp> {
  using OpConversionPattern::OpConversionPattern;
  LogicalResult
  matchAndRewrite(IREE::HAL::InterfaceWorkgroupSizeOp op, OpAdaptor,
                  ConversionPatternRewriter &rewriter) const override {
    rewriter.replaceOpWithNewOp<arith::ConstantIndexOp>(op, 1);
    return success();
  }
};

struct CIMConvertToTargetIRPass final
    : impl::CIMConvertToTargetIRPassBase<CIMConvertToTargetIRPass> {

  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<CIMDialect, affine::AffineDialect, arith::ArithDialect,
                    func::FuncDialect, linalg::LinalgDialect,
                    memref::MemRefDialect, scf::SCFDialect>();
  }

  void runOnOperation() override {
    auto profile = resolveHardwareProfile(getOperation());
    if (failed(profile))
      return signalPassFailure();
    auto isLogicalType = [](Type type) {
      auto memref = dyn_cast<MemRefType>(type);
      return !memref || !memref.getMemorySpace();
    };
    auto isLogicalOp = [&](Operation *op) {
      if (auto global = dyn_cast<memref::GlobalOp>(op))
        return isLogicalType(global.getType());
      return llvm::all_of(op->getOperandTypes(), isLogicalType) &&
             llvm::all_of(op->getResultTypes(), isLogicalType);
    };
    auto legalFunc = [&](func::FuncOp op) {
      auto exportOp = getEntryPoint(op);
      if (!llvm::all_of(op.getArgumentTypes(), isLogicalType) ||
          !llvm::all_of(op.getResultTypes(), isLogicalType))
        return false;
      return !exportOp ||
             (op.getNumArguments() == 0 && op.getNumResults() == 0);
    };
    auto fits = [](Value value, unsigned dim, int64_t capacity) {
      int64_t size = cast<MemRefType>(value.getType()).getDimSize(dim);
      if (!ShapedType::isDynamic(size))
        return size <= capacity;
      auto upper = ValueBoundsConstraintSet::computeConstantBound(
          presburger::BoundType::UB, {value, dim},
          /*stopCondition=*/nullptr, ValueBoundsOptions{/*closedUB=*/true});
      return succeeded(upper) && *upper <= capacity;
    };
    auto legalMvm = [&](MvmOp op) {
      return isLogicalOp(op) && fits(op.getSrc(), 1, profile->arrayRows) &&
             fits(op.getDst(), 1, profile->arrayCellColumns());
    };

    ConversionTarget target(getContext());
    target.addLegalOp<ModuleOp, func::ReturnOp, affine::AffineApplyOp,
                      affine::AffineMinOp, scf::ForOp, scf::YieldOp>();
    target.addDynamicallyLegalOp<
        memref::GlobalOp, memref::GetGlobalOp, memref::ViewOp, memref::CastOp,
        memref::SubViewOp, memref::TransposeOp, memref::AssumeAlignmentOp,
        memref::AllocOp, memref::CopyOp, EltOp>(isLogicalOp);
    target.addDynamicallyLegalOp<MvmOp>(legalMvm);
    target.addLegalOp<arith::ConstantOp, IREE::HAL::InterfaceConstantLoadOp,
                      IREE::HAL::InterfaceWorkgroupIDOp,
                      IREE::HAL::InterfaceWorkgroupCountOp>();
    target.addDynamicallyLegalOp<IREE::HAL::InterfaceBindingSubspanOp>(
        isLogicalOp);
    target.addDynamicallyLegalOp<func::FuncOp>(legalFunc);
    target.addLegalOp<IREE::Codegen::DispatchConfigOp>();
    target.markOpRecursivelyLegal<IREE::Codegen::DispatchConfigOp>();
    target.addIllegalOp<UnrealizedConversionCastOp>();
    target.markUnknownOpDynamicallyLegal([](Operation *) { return false; });

    RewritePatternSet patterns(&getContext());
    SymbolTableCollection symbols;
    patterns.add<ConvertZeroFill>(&getContext(), symbols);
    patterns.add<ConvertWorkgroupSize>(&getContext());
    if (failed(
            applyFullConversion(getOperation(), target, std::move(patterns))))
      signalPassFailure();
  }
};
} // namespace

} // namespace mlir::iree_compiler::IREE::CIM
