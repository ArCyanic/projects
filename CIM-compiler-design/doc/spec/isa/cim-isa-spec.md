# CIM ISA 指令 SPEC

## 1. 文件格式

UTF-8文本，由export section和指令行组成：

```text
section     ::= (".deployment" | ".runtime") "@" export_name
instruction ::= array_load | bit | elt | mem_copy
```

Section按export顺序界定后续指令的lifecycle role。Operands使用逗号加空格分隔；维度使用十进制整数。
Comments不是canonical payload。

Buffer operand按storage打印。SRAM是裸地址；host binding与embedded payload data保留storage tag，
使program没有来源不明的地址：

```text
operand ::= address
          | "binding" "[" ordinal ", " address "]"
          | "embedded" "[" address "]"
```

SRAM地址保留IREE executable的workgroup参数化语义：

```text
address ::= base ("+" coefficient "*" axis)*
axis    ::= "x" | "y" | "z"
```

`base`与`coefficient`是非负十进制byte数。地址在当前workgroup `(x, y, z)` 上求值；静态地址就是只有
`base`的退化形式。裸地址相对当前workgroup的SRAM root，`binding[ord, ...]`相对该dispatch binding range，
`embedded[...]`相对payload的embedded data。该文本直接表达一份可复用的workgroup program，不展开
per-workgroup address table。

## 2. 通用值域

| 名称 | 值域 |
| --- | --- |
| dtype | `i8` / `i16` / `i32` |
| elt op | `add` / `sub` / `mul` / `div` |
| mode | `vv` / `vi` |
| SRAM address | non-negative affine byte address over workgroup `x/y/z` |
| Array `row` / `bit_col` | non-negative；`row`单位为row，`bit_col`单位为physical bit-column |
| Array `K` / `N` | non-negative extent；`N`单位为i8 cell（乘8得physical bit-column） |

Integer使用signed two's-complement。Widening sign-extend；narrowing保留低位；integer result按目标bit width
modular wrap。

## 3. Physical program projection

Final text是linked physical program的**1:1 per-op projection**：deployment中的`cim.array.load`和runtime
中的`cim.bit/elt/mem_copy`各生成一条指令，顺序与program order一致。Bit-serial reconstruction及其
scratch已经在IR中物化，printer只需从native views与hardware profile读取最终地址和尺寸。

Array memref使用byte columns。对static rank-2 Array view：

```text
row      = byte_offset / array_row_stride_bytes
byte_col = byte_offset % array_row_stride_bytes
bit_col  = byte_col * 8
K        = extent0
N        = extent1
```

这些coordinates是native view的lossy projection，不是第二placement owner。`weight_pos`采用origin + extent
形式（`row, bit_col, K, N`四个平铺operand，`N`以i8 cell计），
与赛题基础指令的bracketed corner形式的差异及理由见`doc/contest-detail.md` §4.1.3。Deployment weight
source只允许target-local immutable global，投影为`embedded[byte_offset]`。

## 4. `cim.array.load.i8`

```text
cim.array.load.i8 source, row, bit_col, K, N
```

Source：

```text
embedded[byte_offset]
```

语义：从dense row-major i8 source读取`K x N` bytes，将每个i8按硬件weight encoding写入Array：

```text
[row,row+K) x [bit_col,bit_col+N*8)
```

Load只允许出现在`.deployment @__cim_array_init`段。每个unique region初始化一次，regions不得重叠；
Bounds必须落在profile Array内，`bit_col`必须8-bit aligned。

## 5. `cim.bit.<inputType>.<weightType>`

```text
cim.bit.<inputType>.<weightType>
  dst, src, index, row, bit_col, K, N
```

字段：

| 字段 | 含义 |
| --- | --- |
| dst | i32 raw partial的SRAM byte address |
| src | activation SRAM byte address |
| index | activation bit index |
| row/bit_col | 已初始化weight matrix origin |
| K/N | logical weight shape |

语义：

```text
for j in 0..N-1:
  dst[j] = wrap_i32(sum k in 0..K-1:
    bit_select(src[k], index) * sign_extend_i32(array_weight[k,j]))
```

`cim.bit`只写raw partial，不乘`2^index`，不解释sign bit。Signed reconstruction由后续`elt`显式表达。
Competition v1支持`i8xi8`和`i32xi8`。

每条`cim.bit`行是IR里一个`cim.bit` op的1:1投影，不是`cim.mvm`的展开产物：展开发生在
`cim-expand-bit-serial`，见第9节。

校验：

- `index < bitwidth(inputType)`；
- destination按i32对齐，source按inputType对齐；
- weight范围已由deployment段的`cim.array.load`完整定义；
- Array bounds合法，`bit_col`按weight bit width对齐。

## 6. `elt.<op>.<dtype>.vv`

```text
elt.<op>.<dtype>.vv dst, src1, src2, length
```

```text
for i in 0..length-1:
  dst[i] = wrap_dtype(src1[i] op src2[i])
```

`div` toward zero；除数0不在v1执行语义内。

## 7. `elt.<op>.<dtype>.vi`

```text
elt.<op>.<dtype>.vi dst, src1, immediate, length
```

```text
for i in 0..length-1:
  dst[i] = wrap_dtype(src1[i] op wrap_dtype(immediate))
```

Immediate为signed decimal integer。`2147483648`通过i32 wrap表达sign-bit scale。

## 8. `mem.copy.<dstType>.<srcType>`

```text
mem.copy.<dstType>.<srcType> dst, src, length
```

源和目标使用相同整数类型，`length`为元素数。`dst`与`src`各自可以是SRAM裸地址、
`binding[ordinal, address]`或`embedded[address]`，因此本指令拥有physical program的全部copy：
SRAM-to-SRAM move、embedded constant（bias、zero block）导入，以及host binding的input import与
output export。它们不被过滤，每条都打印：

```text
mem.copy.i32.i32 0, embedded[0], 128
mem.copy.i8.i8 512, binding[0, 0+1024*x], 1024
mem.copy.i32.i32 binding[2, 0+2048*x], 5632, 512
```

## 9. Bit-serial reconstruction

`cim-expand-bit-serial`在serialization之前把每个logical `cim.mvm`改写成下列op序列；final text只是逐条
打印它。对signed `B`-bit activation：

```text
acc = cim.bit(..., 0)
for bit in 1..B-2:
  tmp = cim.bit(..., bit)
  tmp = elt.mul.i32.vi tmp, 2^bit
  acc = elt.add.i32.vv acc, tmp
tmp = cim.bit(..., B-1)
tmp = elt.mul.i32.vi tmp, 2^(B-1)
acc = elt.sub.i32.vv acc, tmp
```

`tmp`是IR里一个真实的`N x i32` SRAM allocation，与其他SRAM buffer一样由SRAM allocator分配arena offset、
计入capacity、并带上workgroup参数项；projection不在arena之外发明scratch region，也不重排physical ops。
`i32xi8`直接得到i32 result，不存在i64临时结果。

## 10. Sequencing

Final line order逐条保持linked physical program order，其中包含每条MVM内部的bit reconstruction顺序。
Projection不选择地址、不重排跨op dependencies，也不成为第二schedule owner。

Init export先以`.deployment @__cim_array_init`打印Array loads；compute exports随后各以`.runtime @name`
打印bit/elt/copy。Section name拥有deployment/runtime分组语义，不改变其内部instruction semantics。
