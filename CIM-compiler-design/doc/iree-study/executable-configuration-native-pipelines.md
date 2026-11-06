# IREE 原生 executable-configuration pipelines

本文说明各 backend 的配置管线及其作用域。

## 1. 调用边界

HAL 对每个 `hal.executable` 建立配置 pipeline，再把 backend pipeline 嵌套到每个
`hal.executable.variant` 上独立执行：

- backend hook 的契约是配置一个 variant 的内容并写入翻译所需注解
  （[TargetBackend.h:145](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Dialect/HAL/Target/TargetBackend.h#L145)）。
- `ConfigureExecutablesPass` 为每种 target 添加 nested variant pass
  （[ConfigureExecutables.cpp:129](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Dialect/HAL/Transforms/ConfigureExecutables.cpp#L129)）。
- variant pass 根据自身 `ExecutableTargetAttr` 构造并运行 backend pipeline
  （[ConfigureExecutables.cpp:62](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Dialect/HAL/Transforms/ConfigureExecutables.cpp#L62)）。

`ConfigureTargetExecutableVariantsPass::runOnOperation()` 的 operation 就是一个
`hal.executable.variant`；它在该 variant 上运行 backend 返回的完整 pipeline
（[ConfigureExecutables.cpp:62](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Dialect/HAL/Transforms/ConfigureExecutables.cpp#L62)、
[ConfigureExecutables.cpp:95](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Dialect/HAL/Transforms/ConfigureExecutables.cpp#L95)）。因此下文的
`ModuleOp` 都是**单个 variant 内部的 module**，不是包含全模型、全部 executable 或全部 variants 的顶层
module。Module pass 可以遍历该 variant 内的多个 entry，但不因此获得跨 variant 视野。

## 2. 所有 backend 共享的前处理

每个调查对象的 target hook 都先加入同一段 variant-scope 前处理，再进入各自 inner-module pipeline。

| Pass | 粒度 | 职责 |
| --- | --- | --- |
| `SpecializeExports` | per-variant / per-export | 根据已知 workload range 专门化 exported function。 |
| `CreateDispatchConfig` | per-variant / per-export | 把每个 export 的 workgroup-count region 克隆为 inner module 中的 `iree_codegen.dispatch_config`，供 codegen 更新。 |
| `TypePropagation` | per-entry | 传播 tensor element type，避免非法 bit-width 的边界 load/store。 |
| `BubbleUpOrdinalOps` | per-entry | 上提 workload ordinal 相关计算，使 workgroup count 能追溯 slice/workload。 |
| `BufferizeCopyOnlyDispatches` | per-entry | 把纯接口 copy dispatch 转成 backend 可继续处理的 `linalg.generic` copy。 |
| `DecomposeSoftmax` | per-entry | 把 softmax 分解为 linalg 运算。 |
| `ConvertAttentionToOnlineAttention` | per-entry | 把 attention 改写为 online-attention 形式。 |

Variant-scope 前处理由公共 builder 组装
（[Common/Passes.cpp:16](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/Common/Passes.cpp#L16)）；后五个由
`addCommonTargetExecutablePreprocessingPasses` 统一组装
（[Common/Passes.cpp:27](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/Common/Passes.cpp#L27)）。

## 3. Backend 对比

### 3.1 总览

Target hook 只接线，不拥有策略：LLVMCPU
[hook](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/plugins/target/LLVMCPU/LLVMCPUTarget.cpp#L252)、VMVX
[hook](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/plugins/target/VMVX/VMVXTarget.cpp#L123)、CUDA
[hook](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/plugins/target/CUDA/CUDATarget.cpp#L457) 和 Vulkan
[hook](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/plugins/target/VulkanSPIRV/VulkanSPIRVTarget.cpp#L364) 都是先加共享 variant 前处理，再 nest 到
inner `ModuleOp`。

### 3.2 LLVMCPU

LLVMCPU 在共享前处理之后实际加入：

| Pass | 粒度 | 职责 |
| --- | --- | --- |
| `MaterializeTuningSpecs` | variant-inner module | 装入并合并 tuning transform libraries，暂存为 module attribute；不分析多个 variants。 |
| `MaterializeUserConfigs` | module orchestration；逐 entry 应用 | 优先物化用户/调优给定的 `translation_info` 与 `lowering_config`。实现显式遍历 module 中的 function（[MaterializeUserConfigs.cpp:188](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/Common/MaterializeUserConfigs.cpp#L188)）。 |
| `MaterializeDeviceEncoding` | per-entry | 按 executable target 物化 encoded tensor layout。 |
| `CPUPropagateDataLayout` | per-entry | 在一个 dispatch 内传播 pack/unpack/reshape layout。 |
| `RematerializeParallelOps` | per-entry | 将 parallel producer 重物化并合入 consumer。 |
| `InsertBatchDimForBatchlessConv` | per-entry | 恢复被上游消去的 unit batch 维，使卷积 pattern 可识别。 |
| `ExpandF16OpToF32` | per-entry | 将当前 CPU 路径不直接处理的 f16 运算扩为 f32。 |
| `ConvertAccGEMMToGEMM` | per-entry | 将 accumulating GEMM 规范成普通 GEMM。 |
| `EraseHALDescriptorTypeFromMemRef` | per-entry | 删除暂未贯通的 HAL descriptor memory-space 标记。 |
| `BufferizeDispatchTensorLoadStore` | per-entry | 把 dispatch tensor 边界转成 codegen buffer load/store。 |
| `CombineResultLayoutTransformation` | per-entry | 将 reshape/transpose 等结果 layout chain 合成 `map_store`。 |
| `LLVMCPUSelectLoweringStrategy` | variant-inner module；逐 entry/root | 若无用户配置，按 entry 的 compute ops 选 root、pipeline 与 tiling config，并为该 entry 的相关 compute ops 写 config。 |

关键边界见 `initCPULaunchConfig`：它只读取一个 `FunctionOpInterface` 的 compute ops
（[KernelDispatch.cpp:4096](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMCPU/KernelDispatch.cpp#L4096)）；root
选择和后续 config 传播也局限于这组 ops
（[KernelDispatch.cpp:4042](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMCPU/KernelDispatch.cpp#L4042)）。

### 3.3 VMVX

VMVX 在共享前处理之后只加入：

| Pass | 粒度 | 职责 |
| --- | --- | --- |
| `MaterializeUserConfigs` | module orchestration；逐 entry 应用 | 接受用户预设的 pipeline/config。 |
| `MaterializeDeviceEncoding` | per-entry | 物化 target encoding。 |
| `EraseHALDescriptorTypeFromMemRef` | per-entry | 删除 descriptor memory-space 标记。 |
| `VMVXSelectLoweringStrategy` | variant-inner module；逐 entry/root | 为尚未配置的 entry 选择 VMVX pipeline，并在 root 的 partitionable parallel loops 上设置默认 distribution tile。 |

selector 本身只是遍历 inner-module entries
（[VMVXSelectLoweringStrategy.cpp:36](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/VMVX/VMVXSelectLoweringStrategy.cpp#L36)）。
实际策略从一个 entry 内找 compute root；默认 tile 为 64，只设置可 partition 的 parallel dimensions
（[VMVX/KernelDispatch.cpp:42](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/VMVX/KernelDispatch.cpp#L42)、
[VMVX/KernelDispatch.cpp:132](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/VMVX/KernelDispatch.cpp#L132)）。

### 3.4 CUDA / LLVMGPU

CUDA 直接复用 LLVMGPU configuration pipeline。在共享前处理之外实际加入：

| Pass | 粒度 | 职责 |
| --- | --- | --- |
| `MaterializeDeviceEncoding` | per-entry | 按 GPU target 物化 encoding。 |
| `GPUGeneralizeNamedOps` | per-entry | 将 matmul 等适合 GPU 策略匹配的 named linalg 规范成 `linalg.generic`。 |
| `ROCDLConfigureBufferInstructions` | per-entry | 标注可用 AMD buffer descriptor 的 subspan；在 CUDA 上是 no-op。 |
| `BufferizeDispatchTensorLoadStore` | per-entry | 物化 dispatch tensor 边界。默认启用 layout-combination 时运行。 |
| `GPUCombineLayoutTransformation` | per-entry | 将结果 layout chain 合成 GPU `map_store`。默认启用。 |
| `GPUGeneralizeNamedOps`（再次） | per-entry | 重新 generalize 上一步可能专门化的 op。 |
| `BlockDynamicDimensions` | per-entry | 把已知为静态倍数的 dynamic dimensions 显式分块。 |
| `ConfigTrackingCanonicalizer` | per-entry | canonicalize 时保持 lowering config 与改写后的 op 同步。 |
| `CSE` | per-entry | 消除公共子表达式。 |
| `MaterializeTuningSpecs` | variant-inner module | 装入并合并 GPU tuning specs。 |
| `MaterializeUserConfigs` | module orchestration；逐 entry 应用 | 应用用户/调优配置。 |
| `LLVMGPUSelectLoweringStrategy` | variant-inner module；逐 entry/root | 按 target、root op 和 shape 选择 GPU pipeline、workgroup size 与 lowering config。 |
| `InsertSMTConstraints` / `VerifySMTConstraints` | per-entry；可选 | 仅相关命令行选项开启时生成/验证 pipeline constraints；默认主线不运行。 |

默认启用 layout combination 的 flag 见
[LLVMGPU/Passes.cpp:90](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMGPU/Passes.cpp#L90)。策略选择虽然复杂，输入仍是
单个 entry：它只收集该 function 的 compute ops并在其中选 root
（[LLVMGPU/KernelConfig.cpp:2573](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMGPU/KernelConfig.cpp#L2573)、
[LLVMGPU/KernelConfig.cpp:2617](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMGPU/KernelConfig.cpp#L2617)）。

### 3.5 Vulkan / SPIR-V 的不同结构

SPIR-V 的 configuration 比 LLVMGPU 更薄，没有先物化 device encoding，而是将 encoding 降为 nop：

| Pass | 粒度 | 职责 |
| --- | --- | --- |
| `GPUGeneralizeNamedOps` | per-entry | 将可处理的 named linalg 规范成 generic。 |
| 五个 common target preprocessing passes | per-entry | 与第 2 节相同。 |
| `MaterializeEncodingIntoNop` | per-entry | 丢弃 encoded tensor layout并物化等价 nop layout。 |
| `BufferizeCopyOnlyDispatches` | per-entry | 处理 encoding 清理后出现的 copy-only 边界。 |
| `Canonicalizer` | per-entry | 清理 encoding-to-nop 结果。 |
| `MaterializeUserConfigs` | module orchestration；逐 entry 应用 | 应用用户配置。 |
| `SPIRVSelectLoweringStrategy` | variant-inner module；逐 entry/root | 选择 SPIR-V pipeline、workgroup size 与 lowering config，并逐 entry 校验。 |

pipeline 组装见 [SPIRV/Passes.cpp:631](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/SPIRV/Passes.cpp#L631)，
encoding-to-nop 的三 pass 展开见
[MaterializeEncodingIntoNop.cpp:67](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/Common/MaterializeEncodingIntoNop.cpp#L67)。
selector 明确逐 function 初始化并验证
（[SPIRVSelectLoweringStrategy.cpp:100](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/SPIRV/SPIRVSelectLoweringStrategy.cpp#L100)）。

## 4. 分析粒度结论

| 粒度 | 原生 configuration 中是否存在 | 实际用途 |
| --- | --- | --- |
| per-root | 是 | 识别一个 entry 的 compute root，选择 pipeline 与 tile。 |
| per-entry | 是，主导粒度 | dispatch body 规范化、encoding 处理、workgroup/tile 配置。 |
| per-variant inner module | 是 | 遍历 entries；装入 tuning/user config；不做跨 variant 优化。 |
| 跨 entries 的联合 tile/packing 选择 | 未发现 | 四类 selector 都逐 entry 调用 launch-config helper。 |
| 跨 variants / executables / 全模型选择 | 未发现 | backend hook 在 variant 上被隔离执行。 |

四个 selector driver 的实现形状完全一致：取得当前 variant 的 inner `ModuleOp`，然后
`moduleOp.getOps<FunctionOpInterface>()` 逐 entry 调用 launch-config helper：

- LLVMCPU：[LLVMCPUSelectLoweringStrategy.cpp:253](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMCPU/LLVMCPUSelectLoweringStrategy.cpp#L253)
- VMVX：[VMVXSelectLoweringStrategy.cpp:36](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/VMVX/VMVXSelectLoweringStrategy.cpp#L36)
- LLVMGPU：[LLVMGPUSelectLoweringStrategy.cpp:81](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMGPU/LLVMGPUSelectLoweringStrategy.cpp#L81)
- SPIR-V：[SPIRVSelectLoweringStrategy.cpp:100](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/SPIRV/SPIRVSelectLoweringStrategy.cpp#L100)

launch-config helper 随后只收集传入 entry function 内的 compute ops。它们可以联合处理**同一个 dispatch
entry 内**的 root、producer 和 consumer，但没有读取其他 entry function 来共同选择 tile：LLVMCPU 见
[KernelDispatch.cpp:4107](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMCPU/KernelDispatch.cpp#L4107)，VMVX 见
[VMVX/KernelDispatch.cpp:134](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/VMVX/KernelDispatch.cpp#L134)，LLVMGPU 见
[LLVMGPU/KernelConfig.cpp:2601](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Codegen/LLVMGPU/KernelConfig.cpp#L2601)。SPIR-V 同样由
driver 逐 entry 调用 `initSPIRVLaunchConfig`，在该 function 内选择 root，不进行跨 entry 汇总。

IREE 顶层 HAL pipeline 确实提供通用 `afterPhase(ExecutableConfigurations)` hook，位置恰在 configuration
之后、translation 之前
（[HAL/Transforms/Passes.cpp:366](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Dialect/HAL/Transforms/Passes.cpp#L366)、
[HAL/Transforms/Passes.cpp:411](https://github.com/iree-org/iree/blob/f5834098a9fc0ea58ab7d36074175c6bfeecf574/compiler/src/iree/compiler/Dialect/HAL/Transforms/Passes.cpp#L411)）。但当前调查的
LLVMCPU、VMVX、CUDA/LLVMGPU 与 SPIR-V 都没有在这里放置独立的 backend model-level selector；这只是一个
通用 pipeline extension seam，不是原生 backend precedent。

## 5. 观察到的 configuration 作用域

本调查得到两种可辨认的IREE结构：

1. 若策略只依赖单个 dispatch entry/root，原生共同形状是“共享 variant/entry 规范化 + 一个
   inner-module selector 逐 entry 写最终 config”；VMVX 是最薄实例。
2. 联合观察多个variants或全模型会超出上述四类backend configuration selector的现有粒度；顶层phase hook
   提供技术seam，但当前调查没有找到原生backend在此实现model-level selector的先例。
