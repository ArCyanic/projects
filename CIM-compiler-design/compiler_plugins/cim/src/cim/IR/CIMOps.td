#ifndef CIM_OPS
#define CIM_OPS

include "mlir/IR/OpBase.td"
include "mlir/IR/AttrTypeBase.td"
include "mlir/IR/EnumAttr.td"
include "mlir/Interfaces/SideEffectInterfaces.td"

def CIM_Dialect : Dialect {
  let name = "cim";
  let cppNamespace = "::mlir::iree_compiler::IREE::CIM";
  let summary = "CIM target dialect";
  let useDefaultAttributePrinterParser = 1;
}

def CIM_MS_Array : I32EnumAttrCase<"Array", 1, "array">;

def CIM_MemorySpace : I32EnumAttr<"MemorySpace",
    "CIM physical storage class", [CIM_MS_Array]> {
  let cppNamespace = "::mlir::iree_compiler::IREE::CIM";
  let genSpecializedAttr = 0;
}

def CIM_MemorySpaceAttr : AttrDef<CIM_Dialect, "MemorySpace"> {
  let mnemonic = "memory_space";
  let summary = "CIM physical storage class";
  let parameters = (ins EnumParameter<CIM_MemorySpace>:$value);
  let assemblyFormat = "`<` $value `>`";
}

def CIM_EltAdd : I32EnumAttrCase<"Add", 0, "add">;
def CIM_EltSub : I32EnumAttrCase<"Sub", 1, "sub">;
def CIM_EltMul : I32EnumAttrCase<"Mul", 2, "mul">;
def CIM_EltDiv : I32EnumAttrCase<"Div", 3, "div">;

def CIM_EltOpcode : I32EnumAttr<"EltOpcode", "CIM elementwise opcode",
    [CIM_EltAdd, CIM_EltSub, CIM_EltMul, CIM_EltDiv]> {
  let cppNamespace = "::mlir::iree_compiler::IREE::CIM";
  let genSpecializedAttr = 0;
}

def CIM_EltOpcodeAttr : EnumAttr<CIM_Dialect, CIM_EltOpcode, "elt_opcode">;

def CIM_EltVV : I32EnumAttrCase<"VV", 0, "vv">;
def CIM_EltVI : I32EnumAttrCase<"VI", 1, "vi">;

def CIM_EltMode : I32EnumAttr<"EltMode", "CIM elementwise operand mode",
    [CIM_EltVV, CIM_EltVI]> {
  let cppNamespace = "::mlir::iree_compiler::IREE::CIM";
  let genSpecializedAttr = 0;
}

def CIM_EltModeAttr : EnumAttr<CIM_Dialect, CIM_EltMode, "elt_mode">;

class CIM_Op<string mnemonic, list<Trait> traits = []> :
    Op<CIM_Dialect, mnemonic, traits>;

def CIM_MvmInput : MemRefOf<[I8, I32]>;
def CIM_IntBuffer : MemRefOf<[I8, I16, I32]>;

def ArrayLoadOp : CIM_Op<"array.load"> {
  let summary = "Load a physical weight matrix into the CIM Array";
  let arguments = (ins
    Arg<MemRefOf<[I8]>, "weight source", [MemReadAt<0, FullEffect>]>:$src,
    Arg<MemRefOf<[I8]>, "Array destination", [MemWriteAt<0, FullEffect>]>:$dst
  );
  let assemblyFormat = [{
    `ins` `(` $src `:` type($src) `)` `outs` `(` $dst `:` type($dst) `)`
    prop-dict attr-dict
  }];
  let hasVerifier = 1;
}

def MvmOp : CIM_Op<"mvm"> {
  let summary = "CIM matrix-vector multiply";
  let arguments = (ins
    Arg<CIM_MvmInput, "activation", [MemReadAt<0, FullEffect>]>:$src,
    Arg<MemRefOf<[I8]>, "weight", [MemReadAt<0, FullEffect>]>:$weight,
    Arg<MemRefOf<[I32]>, "destination", [MemWriteAt<0, FullEffect>]>:$dst
  );
  let assemblyFormat = [{
    `ins` `(` $src `,` $weight `:` type($src) `,` type($weight) `)`
    `outs` `(` $dst `:` type($dst) `)` prop-dict attr-dict
  }];
  let hasVerifier = 1;
}

def BitOp : CIM_Op<"bit"> {
  let summary = "CIM bit-serial matrix-vector multiply";
  let description = [{
    Computes `dst[0, n] = sum_k ((src[0, k] >> index) & 1) * weight[k, n]`.
    The selected activation bit is taken unsigned. The negative weight of a
    signed activation's sign bit is reconstructed by the surrounding
    expansion, which subtracts the top round instead of adding it.
  }];
  let arguments = (ins
    Arg<CIM_MvmInput, "activation", [MemReadAt<0, FullEffect>]>:$src,
    Arg<MemRefOf<[I8]>, "weight", [MemReadAt<0, FullEffect>]>:$weight,
    Arg<MemRefOf<[I32]>, "destination", [MemWriteAt<0, FullEffect>]>:$dst,
    I64Attr:$index
  );
  let assemblyFormat = [{
    `ins` `(` $src `,` $weight `:` type($src) `,` type($weight) `)`
    `outs` `(` $dst `:` type($dst) `)` prop-dict attr-dict
  }];
}

def EltOp : CIM_Op<"elt"> {
  let summary = "CIM elementwise operation";
  let description = [{
    In vv mode `src2` is present and `immediate` is absent. In vi mode
    `src2` is absent and `immediate` is present.
  }];
  let arguments = (ins
    Arg<CIM_IntBuffer, "first source", [MemReadAt<0, FullEffect>]>:$src1,
    Arg<Optional<CIM_IntBuffer>, "optional second source",
        [MemReadAt<0, FullEffect>]>:$src2,
    Arg<CIM_IntBuffer, "destination", [MemWriteAt<0, FullEffect>]>:$dst,
    CIM_EltOpcodeAttr:$op,
    CIM_EltModeAttr:$mode,
    OptionalAttr<I64Attr>:$immediate
  );
  let assemblyFormat = [{
    $op $mode `ins` `(` $src1 (`,` $src2^)? `:` type($src1) (`,` type($src2)^)? `)`
    `outs` `(` $dst `:` type($dst) `)` prop-dict attr-dict
  }];
  let hasVerifier = 1;
}

#endif
