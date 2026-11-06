# ADA200 v4 对 CIM Dialect / ISA 的直接参考

## 结论

ADA200 的一手 ISA明确采用两段式物理程序：

```text
tma_ld weight: source memory -> CIM address/box
tmm: act address + weight address + dst address + matmul descriptor
```

这证明Array initialization必须是显式动作。当前CIM以native immutable source view、native Array
destination view和destination-style `cim.array.load`分别表达source、placement与program action；不需要
region handle。

更重要的是，ADA200 compute引用已配置weight address，不重复weight source或多块描述。这直接支持当前
single-weight-position `cim.bit`，并否定旧rectangle-list compute interface。

ADA200 `tmm`本身是overwrite：descriptor携带完整K，指令没有外部accumulator或`is_accum`字段。CIM
`cim.mvm`采用相同边界。IREE产生串行K tiles时，每次MVM写partial，再由显式`cim.elt add`累计；
不为K split扩张MVM语义。

## 1. 权重装载是独立物理动作

`ISA_V0.85.xlsx` 的 `TMA指令` sheet给出：

- row 3：`tma_ld`；
- rows 17-22：`dat_type=weight/act/param`，weight source可选 external memory或 SMEM；
- rows 56-66：Weight/Param load descriptor包含 `global_base_addr`、`cim_base_addr`、二维
  `box_dim`、`box_start`和 global dimensions。

配套架构规范进一步明确：

- `02-ADA200 Arch Spec.docx` paragraph 69：TMA有外部 memory到 TE/CIM的直连 weight通路；
- paragraph 119：LD搬运 Weight/Act，weight可直接进入 CIM；
- paragraphs 189-192：external→CIM使用离线排好布局的 weight；SMEM→CIM需要在线转换为 CIM布局。

所以以下三件事必须分清：

```text
weight source bytes
physical CIM destination
load/program action that changes CIM cell contents
```

旧runtime首次MVM时隐式物化weight的路线已经删除。

### 对 CIM 的直接影响

当前最小结构是：

```mlir
%array_weight = memref.subview %array[...] [K, N]
cim.array.load ins(%weight) outs(%array_weight)
cim.mvm ins(%activation, %array_weight) outs(%output)
```

Source、destination和load action分别由两个memref operands与operation拥有。Dedicated init export由
IREE `util.initializer`调用一次，普通compute export只引用Array view。

### 不需要的扩展

ADA200没有提供 CIM weight unload/readback主线。`tma_st`负责 SMEM到 external memory，并不证明需要
`cim.array.unload`。当前 full-model static image也没有 eviction，因此不新增 unload。

## 2. Activation 不等同于 Weight programming

ADA200 将两条路径分开：

```text
external memory -> SMEM             TMA
SMEM activation -> Tensor Engine    T_LS / tensor address
weight source -> CIM                tma_ld weight
Tensor Engine -> SMEM result        T_LS / tensor address
```

架构规范 paragraph 170说明 Tensor Engine内部 `T_LS`从 SMEM载入 Act、Weight、量化参数，并把结果写回
SMEM。`ISA_V0.85.xlsx` 的 `Config_Reg` rows 62-69则把 `act_addr`、`wgt_addr`、`dst_addr`和
`param_addr`作为 Tensor地址配置；`Tensor指令` row 3的 `tmm`只引用 address/descriptor indices。

这支持当前 compute直接携带 SRAM activation/output operands：

```mlir
cim.mvm ins(%sram_activation, %array_weight) outs(%sram_output)
```

不需要为了“activation进入阵列输入端”再造一个长期 `cim.array.input_load`。只有硬件把 activation
staging暴露成可独立调度、可复用的存储层时，才应新增该 op。

Weight load则改变 Array cells的驻留内容，不能与 activation读取或 原生 `memref.copy`合并。

## 3. Compute 应引用已装载资源

`ISA_V0.85.xlsx` 的 `Tensor指令` sheet显示：

- row 3：矩阵计算指令为 `tmm`；
- rows 7-8：指令引用 tensor address配置和 tensor descriptor；
- rows 17-29：MatMul descriptor保存输出 M/N box、offset和 source K等计算 geometry；
- `Config_Reg` rows 62-69：weight地址与 activation/output地址并列保存。

所以 ADA200 的结构是：load决定 weight source→CIM destination，compute引用已配置的 CIM weight
address。它没有在每次计算中重新描述 weight搬运。

### 对 final ISA 的结论

Final text先用`cim.array.load`定义真实Array write，再让每条bit只引用一个
`row, bit_col, K, N`位置。无需region ID、descriptor table或rectangle list。

确定原则只有两条：

1. load/program拥有 source与 destination；
2. compute只引用已经初始化的physical Array view，不重复拥有weight source。

## 4. Weight layout 是 load contract 的一部分

架构规范 paragraphs 189-192区分：

- external weight已离线排成 CIM layout，可直接进入 CIM；
- SMEM weight需要在线转换为 CIM要求的布局。

因此，仅从 logical `memref<KxNxi8>` shape与 dtype推导 physical bytes并不总是充分。我们的 competition
mainline可以只定义一种 canonical i8 `[K,N] -> row/bit-column` encoding，但必须明确由谁完成 transpose、
bit packing和 source stride解释。

最窄做法是让native memref layout/encoding拥有source布局，`cim.array.load`消费合法source view并写入
Array destination view；不要为ADA200的i4、在线转换或通用DMA descriptor扩展当前Dialect。

## 5. Dependency 指令存在，但当前不需要照搬

`ISA_V0.85.xlsx` 的 `Special 指令` rows 3-12定义 `dep.gen`、`dep.wait`、`dep.rls`，并区分 tensor、
vector、TMA等 engine。架构规范 paragraphs 294、330、334还要求 weight DMA与 TE/VE计算 overlap。

这说明：若未来要并行 weight load和 compute，就必须有依赖 carrier，不能只靠文本顺序猜异步完成。
但比赛当前是单 Array、顺序执行，且明确不要求 instruction scheduling，因此主线仍使用 ordered program，
不新增 event/fence/barrier op。

不要把 ADA200的 dependency register、engine编号或双缓冲流水线搬进当前 CIM ISA。只有真正启用异步
load-compute overlap时，才重新打开这一设计。

## 6. 只应吸收的结构

| ADA200 结构 | 对 CIM 的帮助 | 当前处理 |
| --- | --- | --- |
| `tma_ld weight` | 证明 Array初始化是独立物理动作。 | 必须补齐。 |
| source selector + global/CIM addresses | 证明 load同时需要 source和 destination。 | 用两个native memref views表达。 |
| 2D weight box | 证明 weight programming天然以块为单位。 | 复用rank-2 `[K,N]` source/destination views。 |
| `tmm`引用 address/descriptor | 证明 compute应引用已装载资源。 | MVM/bit只引用一个Array weight位置。 |
| T_LS从 SMEM供给 activation | 支持 activation地址融合进 compute。 | 不新增 activation-load op。 |
| dependency instructions | 证明异步 overlap需要显式依赖。 | 当前顺序主线不引入。 |

以下内容不进入当前设计：TMA gather/permute/slice/concat/reshape、Vector load/store、配置寄存器加载、
i4 weight、通用 DMA descriptor、engine dependency registers、双缓冲和 sparse CSR/COO。

## 7. 源码资料

资料入口：

- `/Users/mac/repos/ada200v4toolchain/docs/private/npu_spec/ISA_V0.85.xlsx`
  - `TMA指令` rows 3-6、17-22、26-66；
  - `Tensor指令` rows 3、7-15、17-29；
  - `Special 指令` rows 3-12；
  - `Config_Reg` rows 62-88。
- `/Users/mac/repos/ada200v4toolchain/docs/private/npu_spec/02-ADA200 Arch Spec.docx`
  - paragraphs 66-71、117-125、163-192、261-295、330-334。

## rx-mlir 低层 Dialect

### 1. TableGen 的真实 surface 很薄

| surface | operands / attrs / results | interface / effect | 源码位置 |
| --- | --- | --- | --- |
| `npu.Data {kind = "weight"}`（CodeGen 文件称 DataWeight） | 无 operand；`kind`是默认值为`"weight"`的字符串；产生一个`AnyRankedTensor`。不存在`DataWeightOp`。 | 无 interface；无显式 memory effect。 | `include/tpu_mlir/Dialect/Npu/IR/NpuOps.td:310-316`；handler实际匹配`DataOp && kind == "weight"`见`lib/Dialect/Npu/Transforms/CodeGen/Ada200/DataWeight.cpp:465-470`。 |
| `npu.LoadWeight` | 一个`AnyRankedTensor input`、一个必填`StrAttr type`；产生一个`AnyRankedTensor output`。 | 无 interface；无显式 memory effect。 | `include/tpu_mlir/Dialect/Npu/IR/NpuOps.td:335-342`。 |
| `npu.MatMul` | `input`、`weight`均为`AnyRankedTensor`；`bias`为`AnyRankedTensor`或`NoneType`；产生一个`AnyRankedTensor output`；没有矩阵转置、量化或地址 attr。 | 声明`NpuTileInterface`的`allowDataSplit`、`backwardSlice`、`getTileBufferBytes`；无显式 memory effect。 | `include/tpu_mlir/Dialect/Npu/IR/NpuOps.td:94,344-354`。 |
| `npu.LoadInput` | 一个`AnyRankedTensor input`、一个默认值为`"feature"`的字符串`kind`；产生一个`AnyRankedTensor output`。 | 只有默认`NpuTileInterface`；无显式 memory effect。 | `include/tpu_mlir/Dialect/Npu/IR/NpuOps.td:326-333`。 |
| `npu.Store` | 一个`AnyRankedTensor input`；仍产生一个`AnyRankedTensor output`。 | 只有默认`NpuTileInterface`；无显式 memory effect。 | `include/tpu_mlir/Dialect/Npu/IR/NpuOps.td:600-606`。 |

这里没有 CIM 专用 type。五条 surface都复用 builtin ranked tensor，optional bias甚至直接复用
`NoneType`。唯一相关的 Npu attribute是`#npu.mem<addr:size, space>`：TableGen明确把它定义为
“tensor memory placement”，字段只有`addr`、`size`和字符串`space`
（`include/tpu_mlir/Dialect/Npu/IR/NpuOps.td:38-46`）；C++ parser/printer也只解析和打印这三个字段
（`lib/Dialect/Npu/IR/NpuOps.cpp:34-50`）。lit test显示它作为 tensor encoding区分 GMEM和CMEM，而
不是`LoadWeight` operand或 attr：weight source在 GMEM，`LoadWeight` result在 CMEM
（`test/Transforms/Npu/CmemWeightAlloc.mlir:13-18,29-37`）。

effect surface同样必须按源码原样理解：文件引入了`SideEffectInterfaces.td`，并能给别的 op声明
`MemoryEffects<[MemWrite]>`（`include/tpu_mlir/Dialect/Npu/IR/NpuOps.td:13-18,318-324`），但上述
五条定义均没有`MemRead`、`MemWrite`、`Pure`或`NoMemoryEffect` trait。也就是说，Ada200 codegen确实
执行搬运，不等于这个 Npu IR已经精确建模了搬运 effect；不能把这项缺失照搬为 CIM contract。

### 2. `DataWeight -> LoadWeight -> MatMul` 是 source、program、compute 三段

lit lowering直接固定了 SSA 链：`top.Weight`先成为`npu.Data {kind = "weight"}`，再经
`npu.LoadWeight`供给`npu.MatMul`；bias则经`npu.LoadInput`进入同一个 MatMul
（`test/Transforms/lowering/Ada200MatMulWeightLowering.mlir:13-19`）。完整低层样例进一步显示
`LoadInput -> MatMul -> Store`包住主计算，而 weight走独立的`Data -> LoadWeight`支路
（`test/Transforms/Npu/CmemWeightAlloc.mlir:8-21`）。因此有价值的不是 op名字，而是三个不同事实：

1. `Data(kind=weight)`拥有 stored source tensor；它不是 Array programming。DataWeight handler只匹配
   `kind == "weight"`，并把 source位置记录为地址和长度
   （`lib/Dialect/Npu/Transforms/CodeGen/Ada200/DataWeight.cpp:465-487`）。
2. `LoadWeight`是显式 programming action。codegen从 input和 output分别取得 memory placement
   （`lib/Dialect/Npu/Transforms/CodeGen/Ada200/LoadWeight.cpp:159-173`），随后把 source写入
   `global_base_addr`、destination写入`cim_base_addr`，并携带二维 K/N box
   （同文件`:189-200`）；发射端明确标记`data_type=Weight`、external source并调用
   `emitLoadWeight`（同文件`:215-228`）。
3. `MatMul`只消费已产生的 weight SSA value。其 codegen分别取得 activation、weight和 destination
   placement，写入`act_addr`、`wgt_addr`、`dst_addr`；可选 bias才写`param_addr`
   （`lib/Dialect/Npu/Transforms/CodeGen/Ada200/Matmul.cpp:50-80`）。M/N/K来自 input/output shape并形成
   compute descriptor（同文件`:37-47,83-92`），最终以三个 tensor descriptor加 config发射 MatMul
   （同文件`:148-164`）。

这条链也由最终 codegen lit gate确认：`LoadWeight` result被分配到 CMEM，TMA descriptor同时出现
`global_base_addr`与`cim_base_addr`，伪汇编为
`tma_ld ..., weight, matmul, external, ...`
（`test/Transforms/Npu/CmemWeightAlloc.mlir:25-42`）。因此，对 CIM 必要的 surface是：stored weight
source、明确的 Array destination/program effect、以及 compute对已初始化 region的引用；不能把
weight load吞进 MatMul，也不能让 MatMul重新拥有 source bytes。

### 3. types、layout与 interface 的边界

`npu.MatMul`的 semantic type contract只有 ranked tensors加 optional none；物理地址和 descriptor都由
后续 placement/codegen补出。`NpuTileInterface`本身是 layer-group planner查询接口，轴约定直接绑定
NCHW/NCDHW，默认提供 split、identity backward slice和零 scratch
（`include/tpu_mlir/Dialect/Npu/IR/NpuTileInterface.td:15-35,40-100`）。MatMul override只允许部分轴切分、
保持 identity slice并返回零 tile buffer
（`lib/Dialect/Npu/IR/NpuTileInterfaceImpls.cpp:229-263`）；LoadInput和Store使用TableGen trait的默认实现。
lit test只验证后二者不会因缺少 tile interface而阻塞 layer grouping
（`test/Transforms/Npu/LayerGroupTmaLsTile.mlir:23-30`）。这是 TPU-MLIR layer-group机制，不是 CIM
load/MVM/store的必要 semantic interface。

weight physical layout也没有进入 op/type。DataWeight codegen观察`Data -> LoadWeight -> MatMul`的 users
来判定 MatMul weight（`lib/Dialect/Npu/Transforms/CodeGen/Ada200/DataWeight.cpp:137-155`），再把 logical
`[K,N]` transpose为`[N,K]`并block（同文件`:185-198`），按 dtype做 K/N alignment并生成独立的
`storageShape`（同文件`:293-319`）。lit test明确显示 logical`tensor<33x9xi8>`仍不变，但 GMEM allocation
按对齐后的640 bytes计算（`test/Transforms/Npu/GmemWeightAlign.mlir:5-11,39-45`）。必要事实是“physical
weight encoding必须由一个 owner投影”；user-walk、隐式 transpose、block size、i4 packing和 storage shape
side data都是 Ada200 backend artifact，不应进入通用 CIM Dialect surface。

### 4. LoadInput / Store 的数据搬运

`LoadInput`与`Store`都是 tensor-in/tensor-out图节点，但 codegen揭示方向相反：普通`LoadInput`用
input/output placement构造 TMA LS descriptor并调用`emitLoadInput`
（`lib/Dialect/Npu/Transforms/CodeGen/Ada200/LoadInput.cpp:201-212,258-313`）；`Store`反转 global/local参数
构造 descriptor并调用`emitStore`
（`lib/Dialect/Npu/Transforms/CodeGen/Ada200/Store.cpp:27-37,44-80`）。必要事实只有 activation从 external
memory进入计算可见存储、result从本地存储回到 external memory这两个 physical boundary。

不应照搬的是独立`LoadInput`/`Store` semantic op、`kind="feature"`字符串、Store产生同型 SSA result、
TMA descriptor分支和NCHW tile interface。若IREE flow/HAL与native memref load/store已经拥有这些边界，
CIM Dialect无需再复制一套 TPU-MLIR graph adapter；只有 final ISA确实要求显式搬运时，才在 owning
projection中投影物理 load/store，并声明真实 memory effects。

### 5. 必要 surface 与不照搬项

| 分类 | 结论 |
| --- | --- |
| 必要 | weight source、Array destination和program action必须分离；program必须有可观察的Array write effect。 |
| 必要 | MatMul/MVM消费已初始化的 weight region，并保留 activation、weight、optional bias、output之间的直接数据依赖。 |
| 必要 | physical weight encoding/layout必须有唯一 owner，并在进入Array前完成确定性投影。 |
| 必要 | 若 final ISA显式搬运 activation/result，projection必须表达 external↔local方向和真实 effects。 |
| 不照搬 | `Data(kind)`/`LoadWeight(type)`字符串分类、同型 tensor pass-through result、`NoneType`占位。 |
| 不照搬 | `#npu.mem<addr:size, "space">`作为 tensor encoding；CIM 使用原生 memref views 表达放置。 |
| 不照搬 | `NpuTileInterface`的NCHW/NCDHW axis contract、layer-group默认方法和per-op tile helper。 |
| 不照搬 | 通过 users猜 compute mode/layout、MatMul专属 K/N alignment、block packing、i4、NPZ/readable weight side data。 |
| 不照搬 | 五条 op缺失memory-effect声明的现状；这只是该低层 Npu Dialect surface不完整，不能成为 CIM precedent。 |
