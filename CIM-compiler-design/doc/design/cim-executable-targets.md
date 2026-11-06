# CIM Executable-Targets 设计

本阶段消费配置好的 `hal.executable.variant`，输出可链接、满足阵列尺寸约束的 buffer-level CIM 程序。
阶段顺序见 [pipeline](../pipeline.md)，算子语义见 [CIM Dialect 规范](../spec/cim-dialect-surface-spec.md)。

## 两层原生管线

函数级管线由 `#iree_codegen.pass_pipeline<"cim-workgroup">` 选择，通过 MLIR named pipeline registry 构造：

```text
TileAndDistributeToWorkgroupsUsingForall
  → DecomposeLinalgGeneric
  → CIMLegalizeArrayTiles
  → DecomposeHorizontallyFusedGemms
  → Canonicalizer
  → BufferizeDispatchTensorLoadStore / Canonicalizer / CSE
  → IREE comprehensive bufferization
  → RemoveSingleIterationLoop
  → EraseHALDescriptorTypeFromMemRef
  → CIMConvertLinalgToCIM / Canonicalizer / CSE
```

`CIMLowerExecutableTargetPass` 只读取已选 pipeline 并运行它。模块级 completion 随后运行：

```text
ReconcileTranslationInfo
  → ResolveWorkgroupCountHints
  → IREEBufferizeConstants
  → DropCompilerHints
  → CIMConvertToTargetIR
  → Canonicalizer / UnrollAnnotatedLoops / Canonicalizer / CSE
```

准确的 pass 组装由 [CIMPasses.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMPasses.cpp) 维护。
本阶段尚不决定 Array 坐标、SRAM 地址或 payload records。

## Workgroup 与 Array tile

对循环序 `[m,n,k]`，两级原生 `lowering_config` 为：

```text
workgroup = [MTile, 0, 0]
array     = [1, NTile, KTile]
```

配置选择不超过容量且能整除维度的均匀 tile。IREE workgroup tiling 沿 M 生成 mapped `scf.forall`；
reconciliation 用原生 HAL workgroup ID/count 表达 grid。一个入口处理 `MTile` 行，网格覆盖 `M/MTile` 个工作组。
`workgroup_size=[1,1,1]` 不表示阵列尺寸。

Array tiling 先用 `tileConsumerAndFuseProducersUsingSCF` 切并行维并融合 producer，再用
`tileAndFuseConsumer` 将逐元素 consumer 纳入 N tile；最后用 `tileUsingSCF` 切归约维 K。
切片、循环和 DPS accumulator 由 MLIR 形成。`CIMLegalizeArrayTilesPass` 给需要展开的循环加 IREE
unroll marker，completion 的原生 `UnrollAnnotatedLoops` 负责展开。

横向 fused contraction 由 IREE 原生 decomposition 还原为普通 contraction，再统一 bufferize。
CIM 不维护第二套 workgroup lowering、tensor slicing 或 padding 机制。

## Buffer-level compute

`LinalgToCIM` 只接受 buffer semantics 的 signed 整数乘加。它同时核对 Linalg `cast` 属性与 scalar body，
要求 activation/output maps 为 `(m,k)` 与 `(m,n)`；RHS `(n,k)` 通过 metadata-only
`memref.transpose` 转为逻辑 `[K,N]`。不支持的语义留在 conversion 中并触发非法操作诊断。

`cim.mvm` 固定为 `[1,K] × [K,N] → [1,N]xi32`，覆盖写 destination。Linalg DPS init 则可能已有值：

- 沿同一 block 向前扫描，若最近的相关访问是同一目标的零 fill 或 zero-global copy，且源与目标无别名，
  MVM 可直接写 destination 并删除初始化。与目标无关的操作不会阻断扫描；未知或可能相关的读写会阻断。
- 否则 MVM 写同形 scratch，再以显式 `cim.elt add` 累入原 destination。K 分块的部分和沿用这一语义。

别名与效应检查复用 MLIR `AliasAnalysis`、`MemoryEffects` 及 HAL binding 身份。
Elt 的 `[1,N]` 结果由原生 rank-reducing subview 转成 `[N]`；identity generic 直接转换为 `memref.copy`。

## 常量与 HAL 接口

编译入口通过 IREE 的 constant-inline 选项，使静态权重随 executable 捕获；`IREEBufferizeConstants`
将其变成 target-local immutable `memref.global/get_global`。链接后的 planner 从 Dense 或 DenseResource
常量与 native views 读取权重；运行时权重不符合静态部署合同。

入口保持原生无参数函数。`hal.interface.binding.subspan`、workgroup ID/count 和 constant load
保留到 serializer，HAL layout 继续拥有 binding ordinal 与访问属性。派生地址由 native memref views 表达，
不建立额外的位置参数 ABI。

## 最终合法性与交接

`CIMConvertToTargetIRPass` 使用明确的 `ConversionTarget` 和 `applyFullConversion`：

| Surface | 交接职责 |
| --- | --- |
| `func.func/return` | 无参数、无结果的导出入口 |
| `cim.mvm/elt` | 已降低的逻辑计算；MVM 尺寸不得超过 profile 容量 |
| `memref.global/get_global/alloc/view/cast/subview/transpose/assume_alignment/copy` | 常量、逻辑缓冲区、地址与拷贝 |
| HAL binding、constant load、workgroup ID/count | 原生调用接口与工作组坐标 |
| `arith.constant`、`affine.apply/min` | 常量与地址表达式 |
| 暂时保留的 `scf.for/yield` | completion 中按 marker 完全展开 |
| 模块级 `iree_codegen.dispatch_config` | 原生配置 carrier |

Workgroup size 被转换为常量 1；剩余零 `linalg.fill` 转为 immutable zero global 到目标的
`memref.copy`。有界动态 extent 可在该转换内部借助 ValueBounds 求上界，但最终展开与规范化后，
交给物理化和 serializer 的 shape/strides 必须静态。

最终 handoff 不含 Tensor、Linalg、bufferization、Codegen boundary ops 或结构循环。
此时 `cim.mvm` 权重仍是未放置的常量视图，计算缓冲区仍保留原来的 binding/global/alloc 来源。
链接随后汇集全部静态权重，执行 MVM 重组、Array planning 与 SRAM 物理化；不会反查已消失的张量图。

## 代码职责

- [CIMLegalizeArrayTiles.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMLegalizeArrayTiles.cpp)：原生 tiling/fusion 的目标适配与 unroll 标记。
- [LinalgToCIM.cpp](../../compiler_plugins/cim/src/cim/Codegen/Conversion/LinalgToCIM.cpp)：buffer-level compute conversion 与零初始化直写。
- [CIMToTarget.cpp](../../compiler_plugins/cim/src/cim/Codegen/Conversion/CIMToTarget.cpp)：零 fill、workgroup size 转换及 pre-link 合法性边界。
- [CIMMVMUtils.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMMVMUtils.cpp)：共享 contraction 语义、别名/效应证明、权重读取和 view 地址归约。
