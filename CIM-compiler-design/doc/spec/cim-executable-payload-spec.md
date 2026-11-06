# CIM Numeric Executable Payload SPEC

```text
hal.executable.binary(format = "cim-executable", data = CimExecutable)
```

## 1. Scope

本文只拥有binary layout和record semantics。HAL invocation、initializer与state lifetime由
`runtime-abi-spec.md`拥有。Payload不保存host submission order或per-workgroup tables。

## 2. Binary layout

```text
Header
ExportDef[export_count]
BufferViewDef[view_count]
ProgramOpDef[program_op_count]
string_table_bytes
data_bytes
```

Records packed、无padding。Unsigned scalar为little-endian `u32`，immediate为little-endian `i64`。

| Record | Bytes |
| --- | ---: |
| Header | 40 |
| ExportDef | 16 |
| BufferViewDef | 48 |
| ProgramOpDef | 32 |

```text
dtype = 1 -> i8
dtype = 2 -> i16
dtype = 4 -> i32
```

## 3. Header

```text
Header {
  magic = "CIMX"
  version = 2
  sram_capacity_bytes
  array_rows
  array_columns_bits
  export_count
  view_count
  program_op_count
  string_table_byte_length
  data_byte_length
}
```

Active hardware profile必须与header一致。Runtime只接受`version = 2`；不做fallback、repair、dtype
reinterpretation或旧layout adapter。`version = 1`的program op list含`kind = 3`（MVM），不兼容读取。

## 4. ExportDef

```text
ExportDef {
  name_offset
  name_length
  program_start
  program_count
}
```

`exports[i]`对应HAL executable export ordinal `i`。Program range选择一段连续ordered operations；同一range
供该dispatch全部workgroups复用。恰有一个名为`__cim_array_init`的deployment export；其余为compute exports。

## 5. BufferViewDef

```text
BufferViewDef {
  storage_kind
  storage_ordinal
  dtype
  rank

  offset_base
  offset_x
  offset_y
  offset_z

  extent0
  extent1

  stride0_bytes
  stride1_bytes
}

storage_kind = 0 sram, 1 binding, 2 embedded_data, 3 array
```

对当前workgroup：

```text
byte_offset = offset_base + offset_x*x + offset_y*y + offset_z*z
extent[d] = static payload extent[d]
```

规则：

- rank只允许1或2；rank-1的extent1固定为1；
- strides来自native memref；
- SRAM offset相对当前workgroup SRAM root；
- binding ordinal直接来自HAL `interface.binding.subspan`，其byte offset与派生view offset组合后相对dispatch binding range；
- embedded offset相对payload `data_bytes`；
- Array offset相对row-major byte storage，competition row stride为512 bytes；
- Array views必须static、rank-2、i8，并落在`array_rows x array_columns_bits/8`内。

只有byte offset可以按workgroup id线性变化；planner和physicalizer生成static shape，payload不保留没有
producer的dynamic extent bound/step字段。

地址常量项、x/y/z 系数、extent 和字节 stride 都必须能表示为非负 `u32`。Serializer
检查归约过程中的整数加乘溢出以及最终字段范围；负系数即使在某个有限 grid 内得到合法
地址，也不能由当前 ABI 编码，必须诊断失败。

Serializer通过MLIR ValueBounds的EQ关系求地址，只允许原生HAL workgroup ID操作的x/y/z结果作为依赖，
再展平成整数线性系数；仍含非线性或floor-div局部变量的表达式无法编码。Subview offset相对
source的逻辑位置，reinterpret_cast offset相对aligned base并覆盖source原offset，memref.view
的byte shift则改变aligned base。序列化沿view链遵循这些原生MemRef语义，最终统一为byte offset。

## 6. ProgramOpDef

```text
ProgramOpDef {
  kind
  view0
  view1
  view2
  op
  mode
  immediate : i64
}

kind = 1 transfer, 2 array_load, 4 elt, 5 bit
op   = 0 add, 1 sub, 2 mul, 3 div
mode = 0 vv, 1 vi
```

Table position是program order，不是stable ID或provenance。`kind = 3`是v1的MVM record，v2不再发射也不再
接受；该enum值retired，不复用。

### 6.1 transfer

```text
view0 = source
view1 = destination
view2 = op = mode = immediate = 0
```

支持binding/embedded/SRAM之间的host import、constant init、host export和SRAM internal copy。Views为
rank-1或同rank、同extent的rank-2。每条transfer都投影为一条final `mem.copy`，binding与embedded operand
带storage tag打印；没有被过滤掉的transfer。

### 6.2 array_load

```text
view0 = immutable source
view1 = Array destination
view2 = op = mode = immediate = 0
```

Source与destination必须是相同shape/dtype的static rank-2 views。Source只允许embedded_data，
destination只允许Array。Operation按native source strides读取，按Array destination strides写入。

所有array_load只能位于唯一`__cim_array_init` export。每个unique destination region恰好初始化一次；
compute export禁止array_load。Payload layout不增加role bit或第二个deployment section。

### 6.3 bit

```text
view0 = activation SRAM view
view1 = Array weight view [K,N]
view2 = i32 destination SRAM view
op = mode = 0
immediate = activation bit index
```

```text
destination[n] = sum_k ((activation[k] >> immediate) & 1) * weight[k,n]
```

选中的activation bit按unsigned取用；record不乘`2^immediate`、不解释sign bit、不accumulate。
`immediate`必须落在`[0, 8*dtype(view0))`。

Activation/destination只允许rank-1或unit-leading rank-2；destination为i32 write-only view。
两者的存储区域必须不重叠，由编译器在logical lowering与SRAM lifetime planning中保证。
K/N由views推导。Bit weighting、signed reconstruction、K split累计都由独立elt records表达。每条bit record只
引用一个完整Array weight view；没有mapping slice、selected set或region list。

一次logical matrix-vector multiply投影为`8*dtype(view0)`轮bit records加其间的elt records，序列由
`cim-expand-bit-serial`在IR里生成，payload不再持有MVM record。

### 6.4 elt

```text
view0 = src1 SRAM
view1 = src2 SRAM for vv; 0 for vi
view2 = destination SRAM
op = add/sub/mul/div
mode = vv/vi
immediate = 0 for vv; signed value for vi
```

Views shape/dtype一致。Integer结果按destination bit width modular wrap；division toward zero。

## 7. Static deployment invariants

- init source是embedded、static、rank-2 i8 view；destination是static、rank-2 i8 Array view；
- Array destination在profile bounds内，unique regions互不重叠；
- 每个compute bit record的weight view由init完整覆盖；
- init无bindings，compute不写Array；
- serializer只投影已验证的linked physical IR，不重新规划或推断lifecycle。
