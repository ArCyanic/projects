# IREE 其他设备的整图资源规划机制调研

> 面向问题：在 IREE/MLIR 体系中，CPU、GPU、CUDA/ROCm、Vulkan/SPIR-V、VMVX 以及类似 AMD AIE 插件这样的设备，是如何实现“整图资源规划”的？我们应当复用哪些基础设施，哪些部分必须由 CIM target 自己实现？

---

## 0. 结论摘要

IREE 中的“整图资源规划”不是一个单独的 monolithic planner，而是分布在几个层次中：

1. **Flow 层**负责把高层 tensor 计算划分为 dispatch region，并把 dense compute 与主机侧控制/数据流分离。
2. **Stream 层**是最接近“整图资源规划”的公共层：它把 tensor program 转成显式异步调度程序，处理 target affinity、资源 lifetime、资源 usage、concurrency、allocation scheduling、timepoint 依赖等。
3. **HAL 层**把 Stream 的抽象资源和调度落到 device、buffer、command buffer、semaphore、executable variant 上。
4. **Codegen/target backend 层**处理每个 dispatch 内部的硬件相关资源规划，例如 CPU 的 tiling/vectorization、GPU 的 workgroup/subgroup/shared memory、CUDA/ROCm 的 PTX/HSACO metadata、SPIR-V cooperative ops、AIE 的 core/DMA/local memory 映射等。

因此，IREE 的做法可以概括为：

```text
整图资源规划 = Flow dispatch 图划分
             + Stream 跨 dispatch 资源/调度/内存 lifetime 规划
             + HAL 设备/队列/命令/同步抽象
             + target-specific dispatch 内资源规划
```

对我们的 CIM 赛题而言，**Stream 的资源 lifetime、affinity、allocation scheduling 是最值得复用/仿照的公共框架**；但 **CIM 阵列权重映射、512KB SRAM 绝对地址分配、cim.bit 指令序列与 bit-level accumulator 调度**都属于 target-specific resource planning，需要自定义 pass。

---

## 1. IREE 中“整图资源规划”的定义

本调研把“整图资源规划”拆成六类能力：

| 能力 | IREE 中通常出现的位置 | 说明 |
|---|---|---|
| Dispatch 划分/融合 | Flow、DispatchCreation | 把 tensor graph 切成可独立执行的 compute region，决定哪些 op 合并到一个 dispatch。 |
| Device placement / affinity | Stream、HAL | 给资源和异步操作赋予目标设备/target affinity。 |
| 跨 dispatch 依赖调度 | Stream | 用 timepoint 和 async execute/cmd ops 表达依赖、并发、等待、信号。 |
| 跨 dispatch 资源 lifetime / allocation | Stream | 将隐式 tensor/resource 管理转成显式 resource allocation/deallocation。 |
| 常量/参数/encoding 规划 | Stream、Encoding、Parameters | 处理常量打包、参数外置、host/device tensor encoding、目标相关 layout。 |
| Dispatch 内局部资源规划 | Codegen backend | 处理 tile size、workgroup、thread/subgroup、shared memory、vector/register/local memory 等。 |

这与 XLA/HLO 中“单一 HLO module 上做 scheduling、buffer assignment、layout assignment”的风格不同。IREE 更偏“分层资源规划”：公共层负责异步资源图，后端层负责硬件约束。

---

## 2. 公共管线：Flow → Stream → HAL → Codegen

### 2.1 Flow：整图计算划分与 dispatch region

IREE Flow dialect 用于建模 execution data flow 和 partitioning。官方文档说明，Flow 以 MLIR value-semantic tensor 为主要数据类型，利用 SSA use-def 关系支持 computation partitioning 和 outlining；高层 linear algebra 计算会被划分成包含 compatible computations 的 dispatch region，最后 outline 成 executables，只留下 dispatch operations 表达执行流。Flow 的 primary unit 是 `dispatch region`，其目标是包含能够安全且高效一起调度的计算。

资源规划意义：

- Flow 决定“整图被切成几个计算单元”。
- Fusion/dispatch creation 的结果直接影响后续内存 lifetime：dispatch 越少，跨 dispatch tensor 越少，但单个 dispatch 内局部资源压力可能越高。
- Flow 仍然主要是 tensor/dataflow 语义，不做最终物理内存分配。

对 CIM 的启示：

- `linear + 后继 elementwise` 应优先形成一个 CIM dispatch region。
- 多个不相关 linear 不应盲目融合，因为它们可能竞争 CIM weight space 和 SRAM。
- 在 Flow 后增加 CIM dispatch legality：检查 region 是否可由 CIM ISA 覆盖。

参考：IREE Flow dialect 文档 [R1]。

### 2.2 Stream：IREE 的公共整图资源规划核心

Stream dialect 是 IREE 中最接近“整图资源调度/资源规划”的层。官方文档明确说，Stream 把 tensor programs 转换成显式调度的异步程序，内容包括：

- placing ops on specific targets；
- partitioning work between targets；
- scheduling work for concurrency；
- encoding tensors into target-specific resources。

Stream 位于 Flow 和 HAL 之间。文档还说明，Stream 会把 tensor values 降为 opaque resources，使用 `stream.tensor.*` 捕获 tensor encoding 信息，再 lowering 到 `stream.async.*` 表达异步 workload，之后 partition、allocate、schedule 成 `stream.cmd.*`。在这一层，buffer 尚未完全分配，device 也尚未完全 resolved，但 Stream IR 携带资源 symbolic size 和 lifetime，使后续分配变得直接。

关键 Stream passes：

| Pass | 作用 | 对整图资源规划的意义 |
|---|---|---|
| `-iree-stream-refine-usage` | whole-program analysis，为未固定 lifetime 的 `!stream.resource<*>` 分配 lifetime/usage | 资源分类：external、staging、constant、transient 等。 |
| `-iree-stream-schedule-execution` | 将 async ops 分区成在单个 device 上原子执行的 execution regions | 整图执行区域形成，保留依赖顺序。 |
| `-iree-stream-schedule-concurrency` | 找出可并发执行的 async ops 并分组 | 并发调度，而不是简单串行拓扑排序。 |
| `-iree-stream-schedule-allocation` | 把隐式 resource 管理转成显式 `stream.cmd.*` allocation/deallocation | 资源 allocation schedule，lowering 后不可再上升回 alias-free tensor 语义。 |
| `-iree-stream-reuse-allocations` | 在不增加 lifetime 的条件下复用 transient allocations | 类似图级临时内存复用。 |
| `-iree-stream-emplace-allocations` | 将结果直接放入已有资源以消除 copy | in-place/resource forwarding。 |
| `-iree-stream-propagate-timepoints` | 跨 whole program 传播 timepoint，减少不必要 host/device waits | 避免过早同步，提高流水与并发。 |
| `-iree-stream-pack-constants` | 打包并分配 fused constant resources | 权重/常量规划的公共基础，但不懂 CIM 阵列坐标。 |
| `-iree-stream-specialize-encodings` / `materialize-encodings` | 根据 affinity/target 细化 tensor encoding | target-specific layout 的桥接点。 |

资源规划意义：

- Stream 是 IREE 对整图资源、lifetime、异步依赖、并发调度的公共抽象层。
- 但 Stream 的资源是抽象 buffer/resource，不是某个后端 scratchpad 的绝对地址表。
- 对 CIM 来说，Stream 可以负责跨 dispatch 的依赖和资源 lifetime，但不能直接生成 `weight_pos=[row0,col0,row1,col1]` 或 SRAM 地址。

参考：IREE Stream dialect 与 Stream passes 文档 [R2] [R3]。

### 2.3 HAL：低层硬件抽象，而不是智能 planner

HAL dialect 表示 IREE Hardware Abstraction Layer，抽象 device、buffer、buffer view、semaphore、command buffer、executable 等。IREE 文档描述 HAL 是一个低层硬件抽象，用于管理 buffers 并向各种 device types 发出异步工作。HAL passes 处理 target device assignment、device selection memoization、executable interface materialization、executable variants 配置、target executable linking/translation 等。

HAL 的重要特征：

- HAL 接近 runtime API，通常不承担复杂编译优化。
- 它接收 Stream 已经显式化的资源/调度信息。
- driver 侧应尽量 thin，避免把调度智能藏在 runtime 中。

CUDA/HIP HAL 设计文档说得很直白：HAL 提供显式低层 GPU 对象控制；**compiler 期望规划 object lifetime、workload schedule 和 synchronization，HAL implementation/driver stack 应是 thin layer，不应该有太多 smarts/magic**。这对我们的 CIM 后端设计非常关键：资源调度应进入编译 pass，而不是放到运行时指令解释器里临时做。

参考：IREE HAL dialect/passes、CUDA/HIP HAL driver 文档 [R4] [R5] [R6]。

### 2.4 Codegen：每个 dispatch 内的 target-specific 资源规划

IREE Codegen dialect 用于保存 lowering 到某个架构时的 compilation state。官方文档说明，backend 会先分析 `hal.executable.variant` 内的 entry function，选择 compilation pipeline，并决定 tile sizes 等参数；后续流程主要消费这些 attribute，而不再做大量 heuristic decisions。这说明 IREE 的 target-specific 规划是显式记录在 IR attribute 中的，而不是隐式藏在 pass 里。

Codegen 层负责：

- lowering config 选择；
- tile size、workgroup tile、thread tile、subgroup/lane mapping；
- dispatch-local bufferization；
- shared/workgroup local memory；
- vectorization；
- target binary generation。

参考：IREE Codegen dialect 与 lowering config 文档 [R7] [R8]。

---

## 3. CPU / LLVMCPU 设备的资源规划方式

### 3.1 设备模型

IREE CPU deployment 使用 LLVM 将 dense computations 编译为 CPU native instruction streams，并可通过 `local-sync` 或 `local-task` HAL device 执行。`local-sync` 是同步单线程 inline 执行，`local-task` 是基于 IREE task system 的异步多线程执行。

整图层面：

- Flow 划分 dispatch；
- Stream 管理 async/resource/lifetime；
- HAL local device 调用 CPU executable；
- Codegen LLVMCPU 生成 native code。

参考：IREE CPU deployment 文档 [R9]。

### 3.2 CPU 的 dispatch 内资源规划

LLVMCPU backend 主要做：

- lowering strategy selection；
- tiling；
- tile-and-fuse producer/consumer；
- vectorization；
- reduction split；
- conversion to LLVM IR；
- workgroup local memory static layout。

`-iree-llvmcpu-assign-workgroup-local-memory` 会扫描 entry block 中 memory space 为 `iree_codegen.workgroup_local` 的 `memref.alloc`，使用 target data layout 计算静态字节布局，并把多个 alloc 重写为对同一个 packed byte allocation 的 `memref.view`，同时把 `workgroup_local_memory` attribute 传播到 `hal.executable.export`。

资源规划含义：

- CPU 通常没有 GPU 那种显式 scratchpad，但 IREE 仍然在 dispatch-local scope 里用 workgroup local memory 的概念表达局部 buffer 布局。
- CPU 的整图内存压力更多由 Stream 的 transient allocation、allocation reuse、timepoint 和 host/device buffer 管理承担。
- LLVMCPU 的 tiling/vectorization 是 dispatch 内部规划，不是整图调度器。

参考：LLVMCPU pass 文档 [R10]。

### 3.3 Bare-metal CPU：显式选择 min-peak-memory

IREE bare-metal guide 在编译命令中推荐 `--iree-stream-partitioning-favor=min-peak-memory`，并说明该选项会为了降低内存消耗而优化最小峰值内存，代价是牺牲 concurrency，适合 single-threaded execution。

这说明 IREE 对资源调度的一个重要设计点是：**在 Stream 层可以选择“更高并发”还是“更低峰值内存”**。

参考：IREE bare-metal deployment 文档 [R11]。

---

## 4. GPU 设备：Vulkan/SPIR-V、CUDA、ROCm/HIP

### 4.1 GPU 的共同结构

IREE GPU 后端的资源规划分为两个层面：

```text
跨 dispatch：Flow/Stream/HAL
dispatch 内：GPU Codegen pipeline
```

跨 dispatch 层面关注：

- dispatch dependency；
- command buffer 录制；
- device queue submission；
- buffer resource lifetime；
- host/device synchronization；
- executable variant selection。

dispatch 内层面关注：

- workgroup tile；
- thread/subgroup/lane 分布；
- shared memory allocation/reuse；
- DMA/coalesced load；
- software pipelining/multibuffering；
- bank conflict reduction；
- target-specific instruction selection。

### 4.2 Vulkan/SPIR-V

Vulkan 后端是 IREE 的 portable GPU support。Vulkan guide 说明 IREE 的 Vulkan HAL 面向 compute-capable Vulkan 实现，运行时 baseline 包括 Vulkan 1.3、compute queue、timelineSemaphore、scalarBlockLayout、synchronization2 等功能。descriptor-set dispatch 是 portable baseline executable ABI，BDA dispatch 是可选更快 ABI。

SPIR-V pass 文档显示，IREE 会将 Linalg ops tile 到 subgroups，并 vectorize 到适合 SPIR-V cooperative ops 的 vector ops；也会 trim SPIR-V target environment 到 compiled module 所需的最小需求。

资源规划含义：

- Vulkan 的整图调度由 Stream/HAL command buffer + timeline semaphore 表达。
- 设备内局部资源由 SPIR-V/GPU codegen pass 控制，例如 subgroup tiling 和 cooperative ops。
- Vulkan runtime 关注队列、descriptor、semaphore、buffer object；不负责重新决定图级调度策略。

参考：Vulkan guide 与 SPIR-V pass 文档 [R12] [R13]。

### 4.3 CUDA

CUDA HAL driver 文档说明：

- IREE 使用 CUDA driver API；
- device 内部创建 stream 用于内存分配和 kernel launch；
- 支持 async allocation，通过 CUDA stream-ordered memory allocation；
- command buffer 有 CUgraph-backed 和 CUstream-backed 两种实现；
- compiler 生成 FlatBuffer，包含 PTX image 和 entry point metadata，包括 workgroup size、dynamic shared memory size 等；
- HAL semaphore 抽象类似 Vulkan timeline semaphore，用于 host/device、device/device 等同步。

资源规划含义：

- CUDA driver 执行已编译好的 command buffer / graph，不重新做整图内存规划。
- dynamic shared memory size 等 dispatch-local resource metadata 由 compiler/codegen 产生。
- Fine-grain dependency 可通过 CUgraph 表达，但依赖关系本身来自 IREE 编译出的 command buffer/timepoint 结构。

参考：CUDA HAL driver 文档 [R5]。

### 4.4 ROCm/HIP

ROCm guide 说明，`iree-rocm-target` 可以指定精确 SKU，例如 `mi300x`，这让 compiler 同时知道 target architecture 和额外硬件细节，例如 compute units；这些信息会影响 compiler heuristics 和 SKU-specific tuning specs。

HIP HAL driver 与 CUDA 类似：支持 async allocation、command buffer 可由 hipGraph 或 hipStream 实现，executable 对应 hipModule，FlatBuffer 包含 HSACO image 和 entry metadata。

资源规划含义：

- ROCm 的 target-specific tuning specs 是 IREE 针对具体硬件资源做规划的重要机制。
- 编译器可以利用 SKU 信息决定 tile size、pipeline、occupancy 等策略。
- HIP runtime 仍然是执行层，compiler 负责 lifetime/schedule/synchronization 规划。

参考：ROCm guide 与 HIP HAL driver 文档 [R6] [R14]。

### 4.5 GPU Common passes：shared memory 与 pipeline

IREE Common/GPU passes 暴露了大量 dispatch-local 资源规划能力：

| Pass | 资源规划含义 |
|---|---|
| `-iree-codegen-gpu-check-resource-usage` | 检查 GPU-specific constraints，例如 shared memory limit。 |
| `-iree-codegen-gpu-apply-tiling-level` | 按 tiling config tile tensor ops，可选择 fuse consumers。 |
| `-iree-codegen-gpu-infer-memory-space` | 推断 alloc_tensor 的 memory space。 |
| `-iree-codegen-gpu-multi-buffering` | 做多缓冲。 |
| `-iree-codegen-gpu-pipelining` | 做 software pipelining。 |
| `-iree-codegen-gpu-promote-matmul-operands` | 为 matmul operand 插入更适合 coalesced load 的 copies。 |
| `-iree-codegen-gpu-reduce-bank-conflicts` | 通过 padding 降低 bank conflict。 |
| `-iree-codegen-gpu-reuse-shared-memory-allocs` | 复用 shared memory allocations，前提是 liveness 不重叠。 |
| `-iree-codegen-reorder-workgroups` | 调整 workgroup id，提高 cache reuse。 |

资源规划含义：

- GPU scratchpad/shared memory 复用是在 dispatch-local 级别做，不是全图级绝对地址分配。
- liveness non-overlap → memory reuse 的思想可直接迁移到 CIM SRAM allocator。
- resource usage check 的模式适合变成 CIM 的 `check-sram-usage`、`check-weight-array-usage`。

参考：Common/GPU pass 文档 [R15]。

---

## 5. Encoding / layout / parameter 规划

### 5.1 Encoding dialect：target-specific layout 的公共接口

IREE Encoding dialect 为 tensor encoding attributes 和相关 ops 提供抽象。它的用途之一是为 matmul 这类 compute-heavy ops 表达 data-tiling。文档说明：

- encoding type attribute 通常经历 verbose encoding → serialized encoding → physical ops/types 三个状态；
- backend 可以定义自己的 resolver，根据 target-specific detail 解释 encoding；
- resolver 需要实现 `LayoutResolverAttr` 和 `LayoutMaterializerAttr`；
- `SpecializeEncoding` 在 Stream 层运行，因为 Stream 层可以看到 affinity 等上下文，并可据此 specialization storage size。

对 CIM 的启示：

- `weight packing`、`CIM row/col layout` 可以建模为 CIM-specific encoding resolver。
- Stream 层有 affinity/context，可以决定某个 tensor 是普通 SRAM tensor、CIM weight tensor、还是 host parameter。
- 但最终 `weight_pos` 仍需要目标 pass 生成，因为 encoding 本身只描述布局，不自动解决二维阵列装箱。

参考：IREE Encoding dialect 文档 [R16]。

### 5.2 Parameters：大权重/常量资源的外置与异步访问

IREE Parameters 文档说明，parameters 是 externalized storage for resources，支持 large resources like model weights 的存储、操作与加载。没有 parameters 时，`.vmfb` 同时包含 code 和 data；使用 parameters 后，大数据可放在 `.gguf`、`.safetensors`、`.irpa` 等外部源中，由 scope/key 标识。

对 CIM 的启示：

- 赛题通常可能把权重作为编译期常量，但如果模型大或要模拟权重加载，IREE Parameters 可以作为“权重对象管理”的上层入口。
- 然而 Parameters 只负责资源外置/加载抽象，不负责把权重映射到 `[row0,col0,row1,col1]`。

参考：IREE Parameters 文档 [R17]。

---

## 6. VMVX / reference target

VMVX 是 IREE 的 portable interpreter / microkernel reference target，兼容 `local-sync`、`local-task`。它主要用于可移植执行、测试和低依赖部署。其整图资源规划仍走 Flow/Stream/HAL，dispatch 内并不会像 CUDA/ROCm/Vulkan 那样做复杂硬件资源优化。

对 CIM 的启示：

- VMVX 可以作为“先保证功能正确”的 reference 模式，但不能帮助解决 CIM 阵列映射或 SRAM 地址规划。
- 可以仿照 VMVX 的简单 target 接入方式先做可运行闭环，再逐步引入资源优化。

参考：IREE deployment configurations 文档 [R18]。

---

## 7. AMD AIE 插件：最接近 CIM 的参考方向

AMD AIE 插件不是 IREE 主仓库稳定内置后端，但它是“自定义 accelerator target 如何接入 IREE”的重要参考。该仓库说明它是面向 AMD NPU/AIE 的 early-phase IREE compiler/runtime plugin。搜索结果和仓库结构显示，它包含：

- compiler plugin；
- runtime plugin；
- AMD-AIE target passes；
- lowering strategy；
- tiling；
- forall-to-cores mapping；
- pack/transpose；
- data layout propagation；
- bufferize-to-allocation；
- DMA packing/canonicalization；
- lowering to AIE/AIR/XCLBin 等。

这说明类似 AIE 的显式数据搬运、局部内存、二维/多核阵列目标，并不是完全靠 IREE 公共 Stream pass 就能解决；它仍然需要 target plugin 中的大量 passes。

与 CIM 的相似点：

| AMD AIE | CIM 赛题 |
|---|---|
| tile/core mapping | weight row/col mapping + linear tile mapping |
| local memory / memory tile | 512KB SRAM |
| DMA / explicit copy | `mem.copy.dstType.srcType` |
| parallel loop to cores | linear/elementwise tile schedule |
| target-specific lowering pipeline | CIM physical program → array.load + bit/elt/mem.copy |
| plugin 注册 target/backend/runtime | 可先只做 compiler backend，后续再 HAL 化 |

对 CIM 的启示：

- 应当把 CIM 作为 target plugin/backend，而不是试图把所有逻辑塞进通用 Stream。
- IREE 公共层负责 dispatch/resource skeleton；CIM plugin 负责阵列、SRAM、ISA。
- 报告中可以把 AMD AIE 说明 scratchpad/阵列 accelerator 的 target passes。

参考：AMD AIE plugin 仓库与相关搜索结果 [R19] [R20]。

---

## 8. 横向对比：不同设备如何分摊整图资源规划

| 设备/后端 | 整图 dispatch 划分 | 跨 dispatch 资源/lifetime | dispatch 内局部资源 | runtime/driver 职责 | 可借鉴点 |
|---|---|---|---|---|---|
| LLVMCPU | Flow | Stream | tiling、fusion、vectorization、workgroup local memory layout | local-sync/local-task 执行 native code | `min-peak-memory` 策略、workgroup local layout、tile-and-fuse |
| Bare-metal CPU | Flow | Stream，显式倾向 min-peak-memory | LLVMCPU 静态代码生成 | 极小 runtime / static library | SRAM 受限时优先降低 peak memory |
| Vulkan/SPIR-V | Flow | Stream/HAL command buffer + timeline semaphore | workgroup/subgroup tiling、cooperative ops | Vulkan buffer/queue/semaphore/descriptor | command buffer 化、timeline 化依赖 |
| CUDA | Flow | Stream/HAL | PTX、workgroup size、dynamic shared memory metadata | CUstream/CUgraph 执行，支持 async alloc | driver thin，规划在 compiler |
| ROCm/HIP | Flow | Stream/HAL | HSACO、SKU-specific tuning、shared memory等 | hipStream/hipGraph 执行，支持 async alloc | target SKU/arch 引导 heuristic |
| VMVX | Flow | Stream/HAL | microkernel/interpreter | reference execution | 可作为功能闭环参考 |
| AMD AIE plugin | Flow/IREE integration | 部分复用 Stream/HAL | core mapping、DMA、local memory、tiling、allocation | XRT/HAL plugin | 自定义 accelerator 需要 target passes |
| CIM 目标 | 可复用 Flow | 可复用/仿照 Stream | 必须自定义 weight/SRAM/ISA | 可先不完整 HAL，直接 emit ISA | 与 AIE/GPU shared memory 类似，但更需要绝对地址规划 |

---

[R1]: https://iree.dev/reference/mlir-dialects/Flow/ "IREE Flow dialect"
[R2]: https://iree.dev/reference/mlir-dialects/Stream/ "IREE Stream dialect"
[R3]: https://iree.dev/reference/mlir-passes/Stream/ "IREE Stream passes"
[R4]: https://iree.dev/reference/mlir-dialects/HAL/ "IREE HAL dialect/passes"
[R5]: https://iree.dev/developers/design-docs/cuda-hal-driver/ "IREE CUDA HAL driver design"
[R6]: https://iree.dev/developers/design-docs/hip-hal-driver/ "IREE HIP HAL driver design"
[R7]: https://iree.dev/reference/mlir-dialects/IREECodegen/ "IREE Codegen dialect"
[R8]: https://iree.dev/developers/lowering-config/ "IREE Lowering Configs"
[R9]: https://iree.dev/guides/deployment-configurations/cpu/ "IREE CPU deployment"
[R10]: https://iree.dev/reference/mlir-passes/CodegenLLVMCPU/ "IREE LLVMCPU passes"
[R11]: https://iree.dev/guides/deployment-configurations/bare-metal/ "IREE bare-metal deployment"
[R12]: https://iree.dev/guides/deployment-configurations/gpu-vulkan/ "IREE Vulkan deployment"
[R13]: https://iree.dev/reference/mlir-passes/CodegenSPIRV/ "IREE SPIR-V passes"
[R14]: https://iree.dev/guides/deployment-configurations/gpu-rocm/ "IREE ROCm deployment"
[R15]: https://iree.dev/reference/mlir-passes/CodegenCommonGPU/ "IREE Common/GPU passes"
[R16]: https://iree.dev/reference/mlir-dialects/Encoding/ "IREE Encoding dialect"
[R17]: https://iree.dev/guides/parameters/ "IREE Parameters"
[R18]: https://iree.dev/guides/deployment-configurations/ "IREE deployment configurations"
[R19]: https://github.com/nod-ai/iree-amd-aie "AMD AIE plugin for IREE"
[R20]: https://github.com/nod-ai/iree-amd-aie/blob/main/compiler/plugins/target/AMD-AIE/iree-amd-aie/Transforms/Passes.cpp "AMD AIE plugin transforms listing"
