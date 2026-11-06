#include "cim/Frontend/CIMNormalizeONNXLinear.h"

#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Linalg/IR/Linalg.h"
#include "mlir/Dialect/Tensor/IR/Tensor.h"
#include "mlir/IR/BuiltinOps.h"
#include "mlir/IR/DialectRegistry.h"
#include "mlir/Pass/PassRegistry.h"
#include "torch-mlir/Dialect/Torch/IR/TorchOps.h"
#include "torch-mlir/Dialect/TorchConversion/IR/TorchConversionDialect.h"
#include "torch-mlir/Dialect/TorchConversion/IR/TorchConversionOps.h"

namespace mlir::iree_compiler::IREE::CIM {
namespace {

using torch::Torch::OperatorOp;
using torch::Torch::ValueTensorType;

class CIMNormalizeONNXLinearPass final
    : public PassWrapper<CIMNormalizeONNXLinearPass, OperationPass<ModuleOp>> {
public:
  MLIR_DEFINE_EXPLICIT_INTERNAL_INLINE_TYPE_ID(CIMNormalizeONNXLinearPass)

  StringRef getArgument() const override { return "cim-normalize-onnx-linear"; }
  StringRef getDescription() const override {
    return "Normalize contest [N,K] integer linear operations";
  }

  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<arith::ArithDialect, linalg::LinalgDialect,
                    tensor::TensorDialect,
                    torch::TorchConversion::TorchConversionDialect>();
  }

  void runOnOperation() override {
    getOperation().walk([&](OperatorOp op) {
      bool gemm = op.getName() == "onnx.Gemm";
      if ((!gemm && op.getName() != "onnx.MatMulInteger") ||
          op->getNumOperands() < 2)
        return;
      if (!gemm && op->getNumOperands() != 2)
        return;
      auto lhsType = dyn_cast<ValueTensorType>(op.getOperand(0).getType());
      auto rhsType = dyn_cast<ValueTensorType>(op.getOperand(1).getType());
      if (!lhsType || !rhsType || !lhsType.hasSizes() || !rhsType.hasSizes() ||
          lhsType.getSizes().size() != 2 || rhsType.getSizes().size() != 2 ||
          lhsType.getSizes()[1] != rhsType.getSizes()[1])
        return;
      // The supported hardware contract is signed i8 weights and signed
      // i8/i32 activations. Leave other ONNX inputs to upstream conversion.
      if (!rhsType.getDtype().isSignedInteger(8) ||
          (!lhsType.getDtype().isSignedInteger(8) &&
           !lhsType.getDtype().isSignedInteger(32)))
        return;
      if (!gemm) {
        auto resultType = cast<ValueTensorType>(op.getResult(0).getType());
        if (!resultType.hasSizes() ||
            resultType.getSizes().back() != rhsType.getSizes()[0])
          return;
      }
      auto transB = op->getAttrOfType<IntegerAttr>("torch.onnx.transB");
      if (gemm && transB && transB.getValue().getSExtValue() != 0 &&
          !lhsType.getDtype().isSignedInteger(32))
        return;
      if (gemm) {
        auto transA = op->getAttrOfType<IntegerAttr>("torch.onnx.transA");
        auto alpha = op->getAttrOfType<FloatAttr>("torch.onnx.alpha");
        auto beta = op->getAttrOfType<FloatAttr>("torch.onnx.beta");
        if ((transA && !transA.getValue().isZero()) ||
            (alpha && !alpha.getValue().isExactlyValue(1.0)) ||
            (beta && !beta.getValue().isExactlyValue(1.0))) {
          op.emitOpError("CIM Gemm normalization requires transA=0, alpha=1 "
                         "and beta=1");
          signalPassFailure();
          return;
        }
      }

      OpBuilder builder(op);
      auto resultType = ValueTensorType::get(
          &getContext(),
          ArrayRef<int64_t>{lhsType.getSizes()[0], rhsType.getSizes()[0]},
          builder.getIntegerType(32, true));
      Value result = lowerMatmul(builder, op, resultType);
      if (gemm && op->getNumOperands() > 2) {
        OperationState add(op.getLoc(), OperatorOp::getOperationName());
        add.addOperands({result, op.getOperand(2)});
        add.addTypes(resultType);
        add.addAttribute("name", builder.getStringAttr("onnx.Add"));
        result = builder.create(add)->getResult(0);
      }
      op.getResult(0).replaceAllUsesWith(result);
      op.erase();
    });
  }

private:
  static Value lowerMatmul(OpBuilder &builder, OperatorOp op,
                           ValueTensorType resultType) {
    auto toBuiltin = [&](Value value) -> Value {
      auto type = cast<ValueTensorType>(value.getType()).toBuiltinTensor();
      type = type.clone(builder.getIntegerType(
          type.getElementType().getIntOrFloatBitWidth()));
      return torch::TorchConversion::ToBuiltinTensorOp::create(
          builder, op.getLoc(), type, value);
    };
    auto type = cast<RankedTensorType>(resultType.toBuiltinTensor())
                    .clone(builder.getI32Type());
    Value zero = arith::ConstantIntOp::create(builder, op.getLoc(), 0, 32);
    Value empty = tensor::EmptyOp::create(builder, op.getLoc(), type.getShape(),
                                          type.getElementType());
    Value init =
        linalg::FillOp::create(builder, op.getLoc(), zero, empty).getResult(0);
    AffineExpr m, n, k;
    bindDims(builder.getContext(), m, n, k);
    SmallVector<AffineMap> maps{
        AffineMap::get(3, 0, {m, k}, builder.getContext()),
        AffineMap::get(3, 0, {n, k}, builder.getContext()),
        AffineMap::get(3, 0, {m, n}, builder.getContext())};
    auto attrs = builder.getNamedAttr("indexing_maps",
                                      builder.getAffineMapArrayAttr(maps));
    Value result = linalg::MatmulOp::create(
                       builder, op.getLoc(), TypeRange{type},
                       ValueRange{toBuiltin(op.getOperand(0)),
                                  toBuiltin(op.getOperand(1))},
                       ValueRange{init}, ArrayRef<NamedAttribute>{attrs})
                       .getResult(0);
    return torch::TorchConversion::FromBuiltinTensorOp::create(
        builder, op.getLoc(), resultType, result);
  }
};

} // namespace

std::unique_ptr<Pass> createCIMNormalizeONNXLinearPass() {
  return std::make_unique<CIMNormalizeONNXLinearPass>();
}

void registerCIMFrontendPasses() {
  PassRegistration<CIMNormalizeONNXLinearPass>();
}

} // namespace mlir::iree_compiler::IREE::CIM
