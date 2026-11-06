#include "cim/Codegen/CIMMVMUtils.h"
#include "cim/IR/CIMDialect.h"
#include "cim/IR/CIMOps.h"
#include "mlir/Dialect/Arith/IR/Arith.h"
#include "mlir/Dialect/Linalg/IR/Linalg.h"
#include "mlir/Dialect/Linalg/IR/LinalgInterfaces.h"
#include "mlir/Dialect/Linalg/Utils/Utils.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/IR/Matchers.h"
#include "mlir/IR/SymbolTable.h"
#include "mlir/Interfaces/FunctionInterfaces.h"
#include "mlir/Pass/Pass.h"
#include "mlir/Transforms/DialectConversion.h"
#include "llvm/ADT/STLExtras.h"

namespace mlir::iree_compiler::IREE::CIM {

#define GEN_PASS_DEF_CIMCONVERTLINALGTOCIMPASS
#include "cim/Codegen/CIMPasses.h.inc"

namespace {
static Value createScratch(PatternRewriter &rewriter, Location loc,
                           Value like) {
  auto sourceType = cast<MemRefType>(like.getType());
  auto type =
      MemRefType::get(sourceType.getShape(), sourceType.getElementType());
  SmallVector<Value> dynamicSizes;
  for (auto [index, size] : llvm::enumerate(type.getShape()))
    if (ShapedType::isDynamic(size))
      dynamicSizes.push_back(memref::DimOp::create(rewriter, loc, like, index));
  return memref::AllocOp::create(rewriter, loc, type, dynamicSizes);
}

static LogicalResult
createElt(PatternRewriter &rewriter, Location loc, Value src1, Value src2,
          Value dst, EltOpcode opcode,
          std::optional<int64_t> immediate = std::nullopt) {
  Value values[] = {src1, src2, dst};
  for (Value &value : values) {
    if (!value)
      continue;
    auto view = flatMVMResult(rewriter, loc, value);
    if (failed(view))
      return failure();
    value = *view;
  }
  EltOp::create(rewriter, loc, values[0], values[1], values[2], opcode,
                src2 ? EltMode::VV : EltMode::VI,
                immediate ? rewriter.getI64IntegerAttr(*immediate)
                          : IntegerAttr{});
  return success();
}

static Operation *zeroInit(Operation *op, Value src, Value weight, Value dst,
                           AliasAnalysis &aliases) {
  if (mayAlias(src, dst, aliases) || mayAlias(weight, dst, aliases))
    return nullptr;
  for (Operation *previous = op->getPrevNode(); previous;
       previous = previous->getPrevNode()) {
    if (auto fill = dyn_cast_or_null<linalg::FillOp>(previous);
        fill && fill.getDpsInitOperand(0)->get() == dst &&
        matchPattern(fill.getInputs()[0], m_Zero()))
      return fill;
    auto copy = dyn_cast_or_null<memref::CopyOp>(previous);
    if (copy && copy.getTarget() == dst) {
      auto get = copy.getSource().getDefiningOp<memref::GetGlobalOp>();
      auto global =
          get ? SymbolTable::lookupNearestSymbolFrom<memref::GlobalOp>(
                    get, get.getNameAttr())
              : memref::GlobalOp{};
      auto elements = global ? dyn_cast_or_null<DenseElementsAttr>(
                                   global.getInitialValueAttr())
                             : nullptr;
      if (global && global.getConstant() && elements && elements.isSplat() &&
          elements.getSplatValue<APInt>().isZero())
        return copy;
    }
    if (memoryAccess(previous, dst, aliases).isModOrRef())
      break;
  }
  return nullptr;
}

struct ConvertContraction final
    : OpInterfaceConversionPattern<linalg::LinalgOp> {
  ConvertContraction(MLIRContext *context, AliasAnalysis &aliases)
      : OpInterfaceConversionPattern(context), aliases(aliases) {}
  AliasAnalysis &aliases;

  LogicalResult
  matchAndRewrite(linalg::LinalgOp op, ArrayRef<Value>,
                  ConversionPatternRewriter &rewriter) const override {
    if (!op.hasPureBufferSemantics() || !isSignedContraction(op))
      return failure();
    Value src = op.getDpsInputOperand(0)->get();
    Value weight = op.getDpsInputOperand(1)->get();
    AffineMap srcMap = op.getMatchingIndexingMap(op.getDpsInputOperand(0));
    AffineMap rhsMap = op.getMatchingIndexingMap(op.getDpsInputOperand(1));
    AffineMap destMap = op.getMatchingIndexingMap(op.getDpsInitOperand(0));
    auto dims = linalg::inferContractionDims(op);
    if (failed(dims) || !dims->batch.empty() || dims->m.size() != 1 ||
        dims->n.size() != 1 || dims->k.size() != 1)
      return failure();
    auto m = getAffineDimExpr(dims->m.front(), op.getContext());
    auto n = getAffineDimExpr(dims->n.front(), op.getContext());
    auto k = getAffineDimExpr(dims->k.front(), op.getContext());
    if (srcMap.getResults() != ArrayRef<AffineExpr>{m, k} ||
        destMap.getResults() != ArrayRef<AffineExpr>{m, n})
      return rewriter.notifyMatchFailure(
          op,
          "CIM requires activation indexing (m,k) and output indexing (m,n)");
    Value dst = op.getDpsInitOperand(0)->get();
    if (cast<MemRefType>(weight.getType()).getRank() != 2 ||
        rhsMap.getNumResults() != 2)
      return failure();
    auto kAxis = rhsMap.getResultPosition(
        getAffineDimExpr(dims->k.front(), op.getContext()));
    auto nAxis = rhsMap.getResultPosition(
        getAffineDimExpr(dims->n.front(), op.getContext()));
    if (!kAxis || !nAxis)
      return failure();
    SmallVector<unsigned> permutation{*kAxis, *nAxis};
    auto map = AffineMap::getPermutationMap(permutation, op.getContext());
    Operation *zero = zeroInit(op, src, weight, dst, aliases);
    if (!map.isIdentity())
      weight = memref::TransposeOp::create(rewriter, op.getLoc(), weight,
                                           AffineMapAttr::get(map));
    if (zero) {
      MvmOp::create(rewriter, op.getLoc(), src, weight, dst);
      rewriter.eraseOp(op);
      rewriter.eraseOp(zero);
      return success();
    }
    Value partial = createScratch(rewriter, op.getLoc(), dst);
    MvmOp::create(rewriter, op.getLoc(), src, weight, partial);
    if (failed(createElt(rewriter, op.getLoc(), dst, partial, dst,
                         EltOpcode::Add)))
      return failure();
    rewriter.eraseOp(op);
    return success();
  }
};

static std::optional<int64_t> integerImmediate(Value value) {
  auto constant = value.getDefiningOp<arith::ConstantOp>();
  auto attr = constant ? dyn_cast<IntegerAttr>(constant.getValue()) : nullptr;
  return attr ? std::optional<int64_t>(attr.getValue().getSExtValue())
              : std::nullopt;
}

static FailureOr<std::tuple<EltOpcode, Value, Value>>
binaryExpression(Value value) {
  Operation *op = value.getDefiningOp();
  EltOpcode opcode;
  if (isa_and_nonnull<arith::AddIOp>(op))
    opcode = EltOpcode::Add;
  else if (isa_and_nonnull<arith::SubIOp>(op))
    opcode = EltOpcode::Sub;
  else if (isa_and_nonnull<arith::MulIOp>(op))
    opcode = EltOpcode::Mul;
  else if (isa_and_nonnull<arith::DivSIOp>(op))
    opcode = EltOpcode::Div;
  else
    return failure();
  return std::make_tuple(opcode, op->getOperand(0), op->getOperand(1));
}

static FailureOr<Value> inputOperand(linalg::GenericOp op, Value value) {
  auto arg = dyn_cast<BlockArgument>(value);
  if (!arg || arg.getOwner() != op.getBlock() ||
      arg.getArgNumber() >= op.getNumDpsInputs())
    return failure();
  return op.getDpsInputOperand(arg.getArgNumber())->get();
}

struct ConvertGeneric final : OpConversionPattern<linalg::GenericOp> {
  using OpConversionPattern::OpConversionPattern;
  LogicalResult
  matchAndRewrite(linalg::GenericOp op, OpAdaptor,
                  ConversionPatternRewriter &rewriter) const override {
    if (!op.hasPureBufferSemantics() || !linalg::isElementwise(op) ||
        op.getNumDpsInits() != 1 ||
        llvm::any_of(op.getIndexingMapsArray(),
                     [](AffineMap map) { return !map.isMinorIdentity(); }))
      return failure();
    Value dst = op.getDpsInitOperand(0)->get();
    Value expr = cast<linalg::YieldOp>(op.getBlock()->getTerminator())
                     .getValues()
                     .front();
    if (auto input = inputOperand(op, expr); succeeded(input)) {
      if (*input != dst)
        memref::CopyOp::create(rewriter, op.getLoc(), *input, dst);
      rewriter.eraseOp(op);
      return success();
    }
    auto binary = binaryExpression(expr);
    if (failed(binary))
      return failure();
    auto [opcode, lhsValue, rhsValue] = *binary;
    auto lhs = inputOperand(op, lhsValue);
    auto rhs = inputOperand(op, rhsValue);
    Value src1, src2;
    std::optional<int64_t> immediate;
    if (immediate = integerImmediate(rhsValue); immediate && succeeded(lhs)) {
      src1 = *lhs;
    } else if (immediate = integerImmediate(lhsValue);
               immediate &&
               (opcode == EltOpcode::Add || opcode == EltOpcode::Mul) &&
               succeeded(rhs)) {
      src1 = *rhs;
    } else if (succeeded(lhs) && succeeded(rhs)) {
      src1 = *lhs;
      src2 = *rhs;
      immediate.reset();
    } else {
      return failure();
    }
    if (failed(createElt(rewriter, op.getLoc(), src1, src2, dst, opcode,
                         immediate)))
      return failure();
    rewriter.eraseOp(op);
    return success();
  }
};

struct CIMConvertLinalgToCIMPass final
    : impl::CIMConvertLinalgToCIMPassBase<CIMConvertLinalgToCIMPass> {
  void getDependentDialects(DialectRegistry &registry) const override {
    registry.insert<CIMDialect, arith::ArithDialect, linalg::LinalgDialect,
                    memref::MemRefDialect>();
  }
  void runOnOperation() override {
    ConversionTarget target(getContext());
    target.addLegalDialect<CIMDialect, memref::MemRefDialect>();
    target.addLegalOp<arith::ConstantOp>();
    target.addIllegalDialect<linalg::LinalgDialect>();
    target.addLegalOp<linalg::FillOp>();
    target.markOpRecursivelyLegal<linalg::FillOp>();
    RewritePatternSet patterns(&getContext());
    AliasAnalysis aliases(getOperation());
    patterns.add<ConvertContraction>(&getContext(), aliases);
    patterns.add<ConvertGeneric>(&getContext());
    if (failed(applyPartialConversion(getOperation(), target,
                                      std::move(patterns))))
      signalPassFailure();
  }
};

} // namespace
} // namespace mlir::iree_compiler::IREE::CIM
