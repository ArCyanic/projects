# CIM Dialect Surface SPEC

## 1. Active surface

| Surface | 唯一职责 |
| --- | --- |
| `#iree_codegen.pass_pipeline<"cim-workgroup">` | 选择CIM executable-targets pipeline。 |
| `#cim.memory_space<array>` | 标记CIM Array storage/view。 |
| `cim.array.load` | 将physical weight source写入Array destination view。 |
| `cim.mvm` | logical level、destination-style、overwrite-only matrix-vector multiplication。 |
| `cim.bit` | physical level、destination-style、单个activation bit的matrix-vector multiplication。 |
| `cim.elt` | destination-style add/sub/mul/div。 |
| 原生 `memref.copy` | 承载全部物理copy，含boundary import/export；不定义重复的CIM copy op。 |

`cim.mvm`与`cim.bit`是同一次Array execution的两级表达：packing、replication与Array planning都在
`cim.mvm`上工作，`cim.bit`只在`cim-expand-bit-serial`之后的physical program里出现。

四个CIM op都有declarative assembly format。本文§3–§7的示例是canonical打印形式，可由
`iree-opt --iree-plugin=cim` 直接解析。

## 2. Memory spaces

```mlir
#cim.memory_space<array>
```

Array的规范元素存储为i8 byte。Hardware profile仍以physical bit-columns描述容量；从Array memref的
byte-column投影到physical bit-column时乘以8。

Competition Array root：

```mlir
memref.global "private" @cim_array
  : memref<1024x512xi8, #cim.memory_space<array>>
```

Array与SRAM placement只使用native `memref.get_global/view/subview/reinterpret_cast`表达。

CIM executable中的`memref.alloc`根唯一表示entry-local SRAM，其派生view继承同一存储来源。
这些memrefs使用默认memory space；不再用另一份SRAM标签重复记录root身份。Array由带
`#cim.memory_space<array>`的global根区分；binding由原生HAL subspan、embedded data由普通global区分。

## 3. `cim.array.load`

```mlir
cim.array.load ins(%source : memref<512x512xi8>)
               outs(%array_weight : memref<512x512xi8, #cim.memory_space<array>>)
```

规则：

- source与destination均为rank-2 memref，logical shape为`[K,N]`；
- destination必须位于`#cim.memory_space<array>`；
- shape与element dtype一致；competition v1只接受i8 weight；
- source来自target-local immutable global、embedded zero block或其native view；
- operation读取source并写destination，不产生result；
- row/column、mapping ID、source kind、descriptor与profile参数均从memref/profile推导，不进入attrs。

`array.load`不是SRAM copy，也不是declarative placement。它是改变Array cells的deployment op；合法主线中
它只出现于唯一`__cim_array_init`，compute functions中禁止出现。

## 4. `cim.mvm`

```mlir
cim.mvm ins(%activation, %weight : memref<1x512xi8>, memref<512x256xi8>)
        outs(%destination : memref<1x256xi32>)
```

数学语义：

```text
destination = activation x weight
```

规则：

- operands均为memref；activation与weight只读，destination只写；
- activation固定为rank-2 `[1,K]`；weight固定为rank-2 logical `[K,N]` native view；
- planning前weight是immutable view；planning后必须是Array view；
- destination固定为i32 rank-2 `[1,N]`；K/N与layout从memref推导；
- K split与任意外部init由显式`cim.elt add`承接；op不携带accumulator或mode attr；
- op没有region list、mask、placement、SRAM offset、payload ordinal或objective attrs。

Planning后的一个`cim.mvm`只引用一个完整physical weight matrix。Horizontal packing与block-diagonal
replication必须先物化到该matrix的Array subviews。

`cim.mvm`是logical level surface，最迟活到`cim-expand-bit-serial`；该pass之后由§5的`cim.bit`承接。

## 5. `cim.bit`

```mlir
cim.bit ins(%activation, %weight : memref<1x512xi8>, memref<512x256xi8, #cim.memory_space<array>>)
        outs(%destination : memref<1x256xi32>) <{index = 3 : i64}>
```

数学语义：

```text
destination[0, n] = sum_k ((activation[0, k] >> index) & 1) * weight[k, n]
```

规则：

- shape契约与`cim.mvm`相同：activation rank-2 `[1,K]`、weight rank-2 `[K,N]`、destination i32 rank-2 `[1,N]`；
- `index`是I64Attr，落在`[0, bitwidth(activation element type))`，由prop-dict承载；
- 被选中的activation bit按unsigned取用；op不乘`2^index`、不解释sign bit、不做accumulate；
- weight位于`#cim.memory_space<array>`——`cim.bit`是physical level，只在Array planning之后存在；
- destination overwrite-only；bit weighting与signed reconstruction由显式`cim.elt`承接。
- physical lowering保证activation与destination的存储不重叠；SRAM分配保留该活跃期约束。

`cim.bit`由`cim-expand-bit-serial`从已验证的`cim.mvm`产生。三个operand继承原操作的类型与形状，
展开循环负责生成合法的`index`。

一个`cim.bit`对应Array执行的一轮。对B-bit activation，展开结果为：

```text
dst = bit(src, weight, 0)
for i = 1 .. B-2: dst += bit(src, weight, i) * 2^i
dst -= bit(src, weight, B-1) * 2^(B-1)
```

中间轮次使用SRAM space里的scratch `memref.alloc`，其offset和capacity占用由SRAM allocator确定。

## 6. `cim.elt`

```mlir
cim.elt <add> <vv> ins(%src1, %src2 : memref<1024xi32>, memref<1024xi32>)
               outs(%dst : memref<1024xi32>)
cim.elt <mul> <vi> ins(%src1 : memref<1024xi32>)
               outs(%dst : memref<1024xi32>) <{immediate = 8 : i64}>
```

`op`与`mode`是位置属性，按EnumAttr的`<add>`、`<vv>`等形式打印；`immediate`只在vi mode出现，由prop-dict承载。

所有buffers固定为rank-1 `[L]` native views。VV使用两个同type、同extent views；VI使用一个view和signed
immediate。Dtype、element count和alias从memref推导。允许`src1`与`dst`相同，表达in-place accumulation。Integer结果按destination bit width做
two's-complement modular wrap；division toward zero。

## 7. 原生 `memref.copy`

```mlir
memref.copy %source, %destination : memref<1024xi32> to memref<1024xi32>
memref.copy %bias, %sram
  : memref<1x256xi32> to memref<1x256xi32>
```

Source与destination使用原生MemRef的同shape、同元素类型约束，允许不同layout和memory space。
Payload编码限制为静态rank-1/2、i8/i16/i32 views。SRAM-to-SRAM、embedded constant import与
host binding import/export共用该操作；serializer直接生成transfer record及ISA `mem.copy`。

## 8. 阶段合法性

| Boundary | Legal CIM surface |
| --- | --- |
| executable-targets | `cim.mvm/elt`、原生`memref.copy`与HAL interface/native views；尚未建立Array placement。 |
| Array planning后 | init function含`cim.array.load`；compute functions含`mvm/elt`及原生`memref.copy`且MVM weight必须位于Array。 |
| entry physicalization后 | compute/copy operands位于SRAM或Array；全部physical copy均为原生`memref.copy`，含boundary import/export。 |
| `cim-expand-bit-serial`后 | `cim.mvm`不再存在；每次Array execution是一个`cim.bit`加显式`cim.elt` reconstruction。 |
| serialization输入 | 只有`array.load/bit/elt`、原生`memref.copy`及HAL interface/native views；不存在`cim.mvm`或未物化placement。 |

## 9. Verifier ownership

- Op verifier只检查context-free shape、dtype、memory space、mode与effects。
- Executable-target legality保证logical MVM tile不超过profile capacity。
- Array planner证明全部Array views同时bounds内、互不重叠，并由唯一init完整初始化每个MVM读取范围。
- SRAM physicalization证明SRAM views落在一个aligned root内。
- TargetBackend只投影verified views和ordered ops，不重新规划或建立重复validator tree。
