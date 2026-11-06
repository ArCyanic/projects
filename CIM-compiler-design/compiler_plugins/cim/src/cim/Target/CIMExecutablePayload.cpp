#include "cim/Target/CIMExecutablePayload.h"

#include "cim/Codegen/CIMMVMUtils.h"
#include "cim/Common/CIMExecutableFormat.h"
#include "cim/Common/HardwareProfile.h"
#include "cim/IR/CIMOps.h"
#include "iree/compiler/Dialect/HAL/IR/HALOps.h"
#include "mlir/Analysis/FlatLinearValueConstraints.h"
#include "mlir/Dialect/Func/IR/FuncOps.h"
#include "mlir/Dialect/MemRef/IR/MemRef.h"
#include "mlir/Dialect/Utils/StaticValueUtils.h"
#include "mlir/IR/SymbolTable.h"
#include "mlir/Interfaces/ValueBoundsOpInterface.h"
#include "llvm/Support/MathExtras.h"
#include "llvm/Support/raw_ostream.h"

namespace mlir::iree_compiler::IREE::CIM {
namespace {

struct ExportDef {
  uint32_t nameOffset, nameLength, programStart, programCount;
};

struct BufferViewDef {
  uint32_t storageKind, storageOrdinal, dtype, rank;
  uint32_t offsetBase, offsetX, offsetY, offsetZ;
  uint32_t extent0, extent1;
  uint32_t stride0Bytes, stride1Bytes;
};

struct ProgramOpDef {
  uint32_t kind, view0, view1, view2, op, mode;
  int64_t immediate;
};

static_assert(sizeof(BufferViewDef) == CIMX_BUFFER_VIEW_DEF_SIZE);
static_assert(static_cast<uint32_t>(EltOpcode::Add) == CIMX_ELT_OP_ADD);
static_assert(static_cast<uint32_t>(EltOpcode::Sub) == CIMX_ELT_OP_SUB);
static_assert(static_cast<uint32_t>(EltOpcode::Mul) == CIMX_ELT_OP_MUL);
static_assert(static_cast<uint32_t>(EltOpcode::Div) == CIMX_ELT_OP_DIV);
struct LinearExpr {
  int64_t terms[4] = {};
  bool valid = true;
  LinearExpr &operator+=(const LinearExpr &rhs) {
    valid &= rhs.valid;
    for (unsigned i = 0; i < 4; ++i)
      valid &= !llvm::AddOverflow(terms[i], rhs.terms[i], terms[i]);
    return *this;
  }
  LinearExpr scale(int64_t value) const {
    LinearExpr result = *this;
    for (int64_t &term : result.terms)
      result.valid &= !llvm::MulOverflow(term, value, term);
    return result;
  }
};

template <typename T>
static void appendScalar(std::vector<uint8_t> &bytes, T value) {
  for (unsigned i = 0; i < sizeof(T); ++i)
    bytes.push_back((uint64_t(value) >> (i * 8)) & 0xFF);
}

static void appendU32(std::vector<uint8_t> &bytes,
                      std::initializer_list<uint32_t> values) {
  for (uint32_t value : values)
    appendScalar(bytes, value);
}

class PayloadBuilder {
public:
  PayloadBuilder(IREE::HAL::ExecutableVariantOp variant) : variant(variant) {}

  FailureOr<CIMExecutableArtifacts>
  build(const ResolvedHardwareProfile &profile);

private:
  FailureOr<LinearExpr> foldIndex(OpFoldResult ofr, func::FuncOp func);
  FailureOr<uint32_t> view(Value value, func::FuncOp func);
  LogicalResult appendProgram(func::FuncOp func);
  uint32_t appendGlobalData(memref::GlobalOp global);
  std::string emitISA(const ResolvedHardwareProfile &profile);

  IREE::HAL::ExecutableVariantOp variant;
  SmallVector<ExportDef> exports;
  SmallVector<BufferViewDef> views;
  SmallVector<ProgramOpDef> program;
  std::vector<uint8_t> strings;
  std::vector<uint8_t> data;
  DenseMap<Value, uint32_t> viewOrdinals;
  DenseMap<Operation *, uint32_t> globalOffsets;
};

FailureOr<LinearExpr> PayloadBuilder::foldIndex(OpFoldResult ofr,
                                                func::FuncOp func) {
  if (auto constant = getConstantIntValue(ofr))
    return LinearExpr{{*constant}};
  ValueDimList dependencies, operands;
  for (auto id : func.getOps<IREE::HAL::InterfaceWorkgroupIDOp>())
    dependencies.emplace_back(id.getResult(), std::nullopt);
  AffineMap map;
  SmallVector<int64_t> coefficients;
  if (failed(ValueBoundsConstraintSet::computeDependentBound(
          map, operands, presburger::BoundType::EQ, ofr, dependencies)) ||
      failed(getFlattenedAffineExpr(map.getResult(0), map.getNumDims(),
                                    map.getNumSymbols(), &coefficients)) ||
      coefficients.size() != operands.size() + 1)
    return emitError(func.getLoc(),
                     "CIM payload address is not linear in workgroup x/y/z"),
           failure();
  LinearExpr result;
  result.terms[0] = coefficients.back();
  for (auto [index, operand] : llvm::enumerate(operands)) {
    auto id = operand.first.getDefiningOp<IREE::HAL::InterfaceWorkgroupIDOp>();
    int64_t &term = result.terms[id.getDimension().getZExtValue() + 1];
    result.valid &= !llvm::AddOverflow(term, coefficients[index], term);
  }
  return result;
}

uint32_t PayloadBuilder::appendGlobalData(memref::GlobalOp global) {
  auto [it, inserted] = globalOffsets.try_emplace(global, data.size());
  if (!inserted)
    return it->second;
  Attribute value = global.getInitialValueAttr();
  ArrayRef<char> raw;
  if (auto dense = dyn_cast<DenseElementsAttr>(value)) {
    raw = dense.getRawData();
    if (dense.isSplat()) {
      for (int64_t i = 0; i < dense.getNumElements(); ++i)
        data.insert(data.end(), raw.begin(), raw.end());
      return it->second;
    }
  } else {
    raw = cast<DenseResourceElementsAttr>(value).getData();
  }
  data.insert(data.end(), raw.begin(), raw.end());
  return it->second;
}

FailureOr<uint32_t> PayloadBuilder::view(Value value, func::FuncOp func) {
  auto found = viewOrdinals.find(value);
  if (found != viewOrdinals.end())
    return found->second;
  BufferViewDef record{};
  LinearExpr address;
  auto root = resolveBufferBase(value, [&](OpFoldResult term, int64_t scale) {
    auto expression = foldIndex(term, func);
    if (failed(expression))
      return failure();
    address += expression->scale(scale);
    return success();
  });
  if (failed(root))
    return failure();
  Value current = *root;
  if (auto op = current.getDefiningOp<memref::GetGlobalOp>()) {
    auto global = SymbolTable::lookupNearestSymbolFrom<memref::GlobalOp>(
        op, op.getNameAttr());
    auto space = dyn_cast_or_null<MemorySpaceAttr>(
        cast<MemRefType>(op.getType()).getMemorySpace());
    if (space && space.getValue() == MemorySpace::Array) {
      record.storageKind = CIMX_STORAGE_ARRAY;
    } else {
      record.storageKind = CIMX_STORAGE_EMBEDDED_DATA;
      address += LinearExpr{{appendGlobalData(global)}};
    }
  } else if (current.getDefiningOp<memref::AllocOp>()) {
    record.storageKind = CIMX_STORAGE_SRAM;
  } else if (auto binding =
                 current
                     .getDefiningOp<IREE::HAL::InterfaceBindingSubspanOp>()) {
    record.storageKind = CIMX_STORAGE_BINDING;
    record.storageOrdinal = binding.getBinding().getZExtValue();
    if (Value byteOffset = binding.getByteOffset()) {
      auto offset = foldIndex(byteOffset, func);
      if (failed(offset))
        return failure();
      address += *offset;
    }
  } else {
    return emitError(current.getLoc())
               << "unsupported CIM payload storage root",
           failure();
  }
  auto type = cast<MemRefType>(value.getType());
  SmallVector<int64_t> strides;
  int64_t offset;
  if (!type.hasStaticShape() || type.getRank() < 1 || type.getRank() > 2 ||
      !(type.getElementType().isInteger(8) ||
        type.getElementType().isInteger(16) ||
        type.getElementType().isInteger(32)) ||
      failed(type.getStridesAndOffset(strides, offset)) ||
      llvm::any_of(strides, ShapedType::isDynamic))
    return emitError(value.getLoc())
               << "CIM payload view requires static rank-1/2 i8/i16/i32 shape "
                  "and strides",
           failure();
  int64_t bytes = type.getElementTypeBitWidth() / 8;
  if (!address.valid ||
      llvm::any_of(address.terms,
                   [](int64_t term) { return !llvm::isUInt<32>(term); }) ||
      llvm::any_of(type.getShape(),
                   [](int64_t extent) { return !llvm::isUInt<32>(extent); }) ||
      llvm::any_of(strides, [bytes](int64_t stride) {
        return stride < 0 || uint64_t(stride) > UINT32_MAX / bytes;
      }))
    return emitError(value.getLoc())
               << "CIM payload geometry requires nonnegative 32-bit fields "
                  "and non-overflowing address arithmetic",
           failure();
  record.dtype = bytes;
  record.rank = type.getRank();
  record.offsetBase = address.terms[0];
  record.offsetX = address.terms[1];
  record.offsetY = address.terms[2];
  record.offsetZ = address.terms[3];
  record.extent0 = type.getDimSize(0);
  record.extent1 = type.getRank() == 2 ? type.getDimSize(1) : 1;
  record.stride0Bytes = strides[0] * record.dtype;
  record.stride1Bytes = type.getRank() == 2 ? strides[1] * record.dtype : 0;
  uint32_t ordinal = views.size();
  views.push_back(record);
  viewOrdinals[value] = ordinal;
  return ordinal;
}

LogicalResult PayloadBuilder::appendProgram(func::FuncOp func) {
  for (Operation &op : func.getBody().front()) {
    ProgramOpDef record{};
    SmallVector<Value> operands;
    bool usesImmediate = false;
    if (auto copy = dyn_cast<memref::CopyOp>(op)) {
      record.kind = CIMX_OP_TRANSFER;
      operands = {copy.getSource(), copy.getTarget()};
    } else if (auto load = dyn_cast<ArrayLoadOp>(op)) {
      record.kind = CIMX_OP_ARRAY_LOAD;
      operands = {load.getSrc(), load.getDst()};
    } else if (auto bit = dyn_cast<BitOp>(op)) {
      record.kind = CIMX_OP_BIT;
      operands = {bit.getSrc(), bit.getWeight(), bit.getDst()};
      record.immediate = bit.getIndex();
    } else if (auto elt = dyn_cast<EltOp>(op)) {
      record.kind = CIMX_OP_ELT;
      operands.push_back(elt.getSrc1());
      if (elt.getSrc2())
        operands.push_back(elt.getSrc2());
      operands.push_back(elt.getDst());
      record.op = static_cast<uint32_t>(elt.getOp());
      record.mode = static_cast<uint32_t>(elt.getMode());
      record.immediate = elt.getImmediate().value_or(0);
      usesImmediate = !elt.getSrc2();
    } else if (isa<CIMDialect>(op.getDialect()) || op.getNumRegions()) {
      return op.emitError(
          "CIM payload cannot serialize leftover CIM or nested-region ops");
    } else
      continue;
    SmallVector<uint32_t> ordinals;
    for (Value operand : operands) {
      auto ordinal = view(operand, func);
      if (failed(ordinal))
        return failure();
      ordinals.push_back(*ordinal);
    }
    record.view0 = ordinals[0];
    record.view1 = usesImmediate ? 0 : ordinals[1];
    if (record.kind == CIMX_OP_ELT || record.kind == CIMX_OP_BIT)
      record.view2 = ordinals.back();
    program.push_back(record);
  }
  return success();
}

static StringRef dtypeName(uint32_t bytes) {
  switch (bytes) {
  case 1:
    return "i8";
  case 2:
    return "i16";
  case 4:
    return "i32";
  }
  llvm_unreachable("unsupported CIM integer type");
}

static void appendAddress(llvm::raw_ostream &os, const BufferViewDef &view) {
  os << view.offsetBase;
  for (auto [coefficient, axis] : llvm::zip_equal(
           ArrayRef<uint32_t>{view.offsetX, view.offsetY, view.offsetZ},
           ArrayRef<StringRef>{"x", "y", "z"}))
    if (coefficient)
      os << "+" << coefficient << "*" << axis;
}

std::string PayloadBuilder::emitISA(const ResolvedHardwareProfile &profile) {
  std::string text;
  llvm::raw_string_ostream os(text);
  uint32_t rowBytes = profile.arrayCellColumns();
  auto exportName = [&](const ExportDef &exportDef) {
    return StringRef(reinterpret_cast<const char *>(strings.data()) +
                         exportDef.nameOffset,
                     exportDef.nameLength);
  };
  // SRAM operands print as a bare address; host bindings and embedded payload
  // data keep the storage tag so the program has no unexplained source.
  auto appendOperand = [&](const BufferViewDef &view) {
    if (view.storageKind == CIMX_STORAGE_BINDING)
      os << "binding[" << view.storageOrdinal << ", ";
    else if (view.storageKind == CIMX_STORAGE_EMBEDDED_DATA)
      os << "embedded[";
    appendAddress(os, view);
    if (view.storageKind == CIMX_STORAGE_BINDING ||
        view.storageKind == CIMX_STORAGE_EMBEDDED_DATA)
      os << "]";
  };
  // Array coordinates are recovered from the planned weight subview: the row
  // is the whole rows the offset spans, the column is the remaining bytes
  // widened to physical bit-columns.
  auto appendWeightPos = [&](const BufferViewDef &weight) {
    os << weight.offsetBase / rowBytes << ", "
       << (weight.offsetBase % rowBytes) * 8 << ", " << weight.extent0 << ", "
       << weight.extent1;
  };
  auto appendExport = [&](unsigned ordinal, StringRef role) {
    const ExportDef &exportDef = exports[ordinal];
    os << "." << role << " @" << exportName(exportDef) << "\n";
    for (const ProgramOpDef &op : llvm::ArrayRef(program).slice(
             exportDef.programStart, exportDef.programCount)) {
      const BufferViewDef &a = views[op.view0], &b = views[op.view1],
                          &c = views[op.view2];
      if (op.kind == CIMX_OP_TRANSFER) {
        os << "mem.copy." << dtypeName(b.dtype) << "." << dtypeName(a.dtype)
           << " ";
        appendOperand(b);
        os << ", ";
        appendOperand(a);
        os << ", " << b.extent0 * b.extent1 << "\n";
      } else if (op.kind == CIMX_OP_ARRAY_LOAD) {
        os << "cim.array.load.i8 ";
        appendOperand(a);
        os << ", ";
        appendWeightPos(b);
        os << "\n";
      } else if (op.kind == CIMX_OP_BIT) {
        os << "cim.bit." << dtypeName(a.dtype) << "." << dtypeName(b.dtype)
           << " ";
        appendOperand(c);
        os << ", ";
        appendOperand(a);
        os << ", " << op.immediate << ", ";
        appendWeightPos(b);
        os << "\n";
      } else if (op.kind == CIMX_OP_ELT) {
        static constexpr StringLiteral names[] = {"add", "sub", "mul", "div"};
        os << "elt." << names[op.op] << "." << dtypeName(c.dtype) << "."
           << (op.mode ? "vi" : "vv") << " ";
        appendOperand(c);
        os << ", ";
        appendOperand(a);
        os << ", ";
        if (op.mode)
          os << op.immediate;
        else
          appendOperand(b);
        os << ", " << c.extent0 * c.extent1 << "\n";
      }
    }
  };
  for (bool deployment : {true, false}) {
    for (unsigned i = 0; i < exports.size(); ++i) {
      if ((exportName(exports[i]) == "__cim_array_init") == deployment) {
        appendExport(i, deployment ? "deployment" : "runtime");
      }
    }
  }
  return text;
}

FailureOr<CIMExecutableArtifacts>
PayloadBuilder::build(const ResolvedHardwareProfile &profile) {
  SmallVector<IREE::HAL::ExecutableExportOp> exportOps(
      variant.getExportOps().begin(), variant.getExportOps().end());
  llvm::sort(exportOps, [](auto a, auto b) {
    return a.getOrdinal()->getZExtValue() < b.getOrdinal()->getZExtValue();
  });
  for (auto exportOp : exportOps) {
    auto func =
        variant.getInnerModule().lookupSymbol<func::FuncOp>(exportOp.getName());
    ExportDef record{};
    record.nameOffset = strings.size();
    record.nameLength = exportOp.getName().size();
    strings.insert(strings.end(), exportOp.getName().begin(),
                   exportOp.getName().end());
    record.programStart = program.size();
    if (failed(appendProgram(func)))
      return failure();
    record.programCount = program.size() - record.programStart;
    exports.push_back(record);
  }

  if (llvm::any_of(ArrayRef<uint64_t>{exports.size(), views.size(),
                                      program.size(), strings.size(),
                                      data.size()},
                   [](uint64_t size) { return !llvm::isUInt<32>(size); }))
    return variant.emitError("CIM payload sections exceed 32-bit size limits"),
           failure();
  std::vector<uint8_t> bytes;
  appendU32(bytes, {CIMX_MAGIC, CIMX_VERSION, profile.sramCapacityBytes,
                    profile.arrayRows, profile.arrayColumns,
                    static_cast<uint32_t>(exports.size()),
                    static_cast<uint32_t>(views.size()),
                    static_cast<uint32_t>(program.size()),
                    static_cast<uint32_t>(strings.size()),
                    static_cast<uint32_t>(data.size())});
  for (const ExportDef &record : exports) {
    appendU32(bytes, {record.nameOffset, record.nameLength, record.programStart,
                      record.programCount});
  }
  for (const BufferViewDef &record : views) {
    const uint32_t *fields = reinterpret_cast<const uint32_t *>(&record);
    for (unsigned i = 0; i < 12; ++i)
      appendScalar(bytes, fields[i]);
  }
  for (const ProgramOpDef &record : program) {
    appendU32(bytes, {record.kind, record.view0, record.view1, record.view2,
                      record.op, record.mode});
    appendScalar(bytes, record.immediate);
  }
  bytes.insert(bytes.end(), strings.begin(), strings.end());
  bytes.insert(bytes.end(), data.begin(), data.end());
  return CIMExecutableArtifacts{std::move(bytes), emitISA(profile)};
}

} // namespace

FailureOr<CIMExecutableArtifacts>
buildCIMExecutableArtifacts(IREE::HAL::ExecutableVariantOp variant) {
  auto profile = resolveHardwareProfile(variant);
  if (failed(profile))
    return failure();
  return PayloadBuilder(variant).build(*profile);
}

} // namespace mlir::iree_compiler::IREE::CIM
