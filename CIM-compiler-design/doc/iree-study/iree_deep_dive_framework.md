# IREE 深度认知框架：从全栈架构到 12 阶段编译演进

很多开发者在初次阅读 IREE 编译管线文档（尤其是直接按 1 到 12 阶段平铺直叙的材料）时，都会产生强烈的割裂感：**为什么前几步还在讨论矩阵乘法和广播，中间突然变成内存字节偏移和时间点（Timepoint），接着又跳回 GPU 线程分块（Tiling），最后却在讲虚拟机字节码（VM Bytecode）？**

造成这种困惑的根本原因，是没有先建立 IREE 最核心的**“主从双轨（Host-Device Dual-Track）”顶层视角**。本文为你重构了一套从顶层设计哲学、双轨分叉演进、底层 MLIR 核心机制，到比赛项目复盘路径的完整认知框架。

## 一、 破局视角：理解 IREE 的顶层设计哲学

在传统的深度学习框架（如 PyTorch）中，运行时（Runtime）非常庞大：Python 或 C++ 主程序在运行期动态解析计算图、调用内存分配器申请显存、查找算子库（如 cuDNN / Metal Performance Shaders）并向 GPU 队列发射 Kernel。

而 IREE（Intermediate Representation Execution Environment）的核心目标是**“将运行时承担的调度与内存管理工作，全部前移到编译期静态完成”**（定义于 [Pipelines.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FPipelines%2FPipelines.cpp%23L77)）。为了做到这一点，IREE 编译器必须同时生成两套程序，并在最终产物 `.vmfb`（VM FlatBuffer）中将它们合二为一：

1. **Host 轨（CPU 控制面 / 调度程序）**：回答“什么时候分配多少字节内存、按什么顺序启动哪些 GPU 任务、用什么信号等待任务完成、如何把结果返回给调用者”。
2. **Device 轨（GPU/NPU 数据面 / 核函数程序）**：回答“在一次 GPU Kernel 启动内部，成百上千个线程如何分工、如何利用向量寄存器和 Subgroup 指令完成算术计算”。

用这一视角重新审视 IREE 原生 12 阶段，你会发现它根本不是一条单向直线，而是一个**“合（图级准备） ──► 分（Host/Device 双轨演进） ──► 合（二进制打包与字节码生成）”**的菱形架构：

| 演进模组 | 架构轨道 | 包含的编译阶段（Phases） | 解决的核心工程问题 | 核心 Dialect 演进 |
| :--- | :--- | :--- | :--- | :--- |
| **模组一：图级准备与规范化** | 统一计算图 | `1. input`、`2. abi`、`3. preprocessing`、`4. global-optimization` | 把前端算子统一为可分析循环结构的代数表示，隔离外部调用接口，并做好算子融合前的图级清理。 | `stablehlo` ──► `linalg` + `hal.tensor` |
| **模组二：任务切分与双轨分叉** | 统一 ──► 分叉点 | `5. dispatch-creation`、`6. flow` | 决定哪些算子融合进同一个 GPU Kernel（Dispatch），并将核函数代码与主控流正式剥离。 | `linalg` ──► `flow.dispatch` + `flow.executable` |
| **模组三：Host 轨资源与异步调度** | Host 控制面 | `7. stream` | 将虚拟的 Tensor 转化为带生命周期的物理字节块（Resource），规划内存复用与异步等待（Timepoint）。 | `flow` ──► `stream.resource` + `stream.cmd` |
| **模组四：Device 轨核函数生成** | Device 数据面 | `8. executable-sources`、`9. executable-configurations`、`10. executable-targets` | 为每个 Kernel 绑定指针接口，决定分块（Tile）与线程映射策略，生成硬件原生指令（SPIR-V / LLVM IR）。 | `linalg` ──► `vector` / `scf` ──► `spirv` |
| **模组五：双轨汇合与运行时落地** | 汇合 ──► 落地 | `11. hal`、`12. vm` | 将 Device 轨编译为硬件二进制载荷，将 Host 轨转化为硬件抽象层命令录制与轻量级 VM 字节码。 | `stream` + `spirv` ──► `hal` ──► `vm` |

## 二、 贯穿案例：残差 MLP 的三个关键追踪锚点

为了看清一个数学公式如何在上述五个模组中被逐步拆解成硬件指令，我们以原文档中的**残差多层感知机（Residual MLP）**为贯穿案例：

```text
输入参数：
  X  : f32[16,32]       W1 : f32[32,64]       b1 : f32[64]
  W2 : f32[64,32]       b2 : f32[32]          R  : f32[16,32]

计算逻辑：
  1. 第一层（隐藏层）：H = max(X @ W1 + broadcast(b1), 0)    # 形状：f32[16,64]
  2. 第二层（残差层）：Y = H @ W2 + broadcast(b2) + R        # 形状：f32[16,32]
  3. 第三层（行归约）：S[i] = sum_j Y[i,j]                   # 形状：f32[16]
  4. 返回结果：return Y, S
```

在深入 12 个阶段时，不需要记住每一行繁琐的 MLIR 语法，只需死死盯住以下**三个中间值（追踪锚点）**的命运变化：

* **锚点 `H`（纯内部临时数据的代表）**：由第一层产生，仅供第二层消费，外部调用者根本不需要看到它。它揭示了编译器**如何做算子融合（把 `bias` 和 `ReLU` 吞进矩阵乘内部）**，以及**如何为跨 Kernel 的临时数据申请用完即毁的瞬态内存（Transient Memory）**。
* **锚点 `Y`（双重身份数据的代表）**：既是第二层的输出，需要作为最终结果之一返回给用户；同时又是第三层行归约的输入。它揭示了编译器**如何处理无法简单原地覆盖的数据依赖，以及如何将多个返回值打包进同一块连续物理内存（Buffer Packing）**。
* **锚点 `S`（跨线程协作归约的代表）**：把 `Y` 的每一行（32 列）加和成 1 个标量。它揭示了在 GPU 编程中，**独立并行计算（矩阵乘）与跨线程协作计算（Subgroup Reduction）在分块和指令生成上的本质差异**。

## 三、 循序渐进：IREE 12 阶段深度拆解

下面我们严格按照“为什么需要这一步（痛点） ──► 做了什么核心决策 ──► IR 发生了什么本质变化”的逻辑，逐一拆解五个模组中的 12 个阶段。

### 模组一：图级准备与规范化（Stages 1–4）

这一模组的目标是：**把五花八门的前端框架算子，清洗成具有统一循环与访存语义的表示，并锁定对外调用接口与目标硬件属性。**

#### Stage 1: `input` —— 擦除前端方言差异，暴露迭代与访存结构

* **当前痛点**：前端模型（如 StableHLO、TOSA、Torch）用高层黑盒算子描述计算（例如 `stablehlo.dot_general` 只说明收缩维度是 `[1] x [0]`，`stablehlo.broadcast_in_dim` 只说明维度扩展）。如果保持这种黑盒状态，后续的循环分块（Tiling）和算子融合（Fusion）引擎就要为几百种算子分别编写规则。
* **核心决策**：通过 [buildStableHLOInputConversionPassPipeline](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fplugins%2Finput%2FStableHLO%2FConversion%2FPasses.cpp%23L42) 将所有计算统一降级到 **[Linalg Dialect](https://www.google.com/search?q=https%3A%2F%2Fmlir.llvm.org%2Fdocs%2FDialects%2FLinalg%2F)**，并由 [IREEImportPublic.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FInputConversion%2FCommon%2FIREEImportPublic.cpp%23L30) 将入口函数统一为 `util.func`。
* **IR 演进本质**：
  * **矩阵乘显式化**：`stablehlo.dot_general` 先经 [DotGeneralToDot.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fplugins%2Finput%2FStableHLO%2FConversion%2FPreprocessing%2FDotGeneralToDot.cpp%23L215) 规范化，再经 [StablehloToLinalgDotProduct.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Fstablehlo%2Fblob%2F46af9d3590bc712d1c9e2f8ef408d2ecbb6108a3%2Fstablehlo%2Fconversions%2Flinalg%2Ftransforms%2FStablehloToLinalgDotProduct.cpp%23L99) 拆解为三步——分配空张量（`tensor.empty`）、清零累加初值（`linalg.fill`）、执行结构化矩阵乘（`linalg.matmul`）。
  * **广播与逐元素计算合一**：`b1` 的广播不再产生真实的中间大张量，而是通过 [StablehloToLinalgPointwise.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Fstablehlo%2Fblob%2F46af9d3590bc712d1c9e2f8ef408d2ecbb6108a3%2Fstablehlo%2Fconversions%2Flinalg%2Ftransforms%2FStablehloToLinalgPointwise.cpp%23L120) 转化为 `linalg.generic` 上的仿射索引映射（Affine Map）：输出点 `(m, n)` 直接去读取 `b1` 的 `(n)` 位置，并在标量计算体（Payload）中一口气完成 `arith.addf`（加偏置）和 `arith.maximumf`（ReLU）。

```mlir
// Stage 1 核心形态：显式暴露初始累加器与 Linalg 结构
%empty = tensor.empty() : tensor<16x64xf32>
%init  = linalg.fill ins(%zero : f32) outs(%empty : tensor<16x64xf32>) -> tensor<16x64xf32>
%mm    = linalg.matmul ins(%x, %w1 : tensor<16x32xf32>, tensor<32x64xf32>)
                       outs(%init : tensor<16x64xf32>) -> tensor<16x64xf32>
```

#### Stage 2: `abi` —— 隔离“外部调用协议”与“内部张量优化”

* **当前痛点**：C/C++ 或 Python 调用编译好的模型时，传入的是指向某块物理内存的句柄（包含数据指针、形状和元素类型校验信息），而不是 MLIR 内部虚拟的 `tensor<16x32xf32>`。但如果过早把函数内部全部改成指针操作，编译器就无法再做全局张量优化了。
* **核心决策**：由 [WrapEntryPointsPass](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FBindings%2FNative%2FTransforms%2FWrapEntryPoints.cpp%23L41) 建立“外层 Buffer View 协议 + 内层 Tensor 计算”的三明治结构。
* **IR 演进本质**：公开函数 `@main` 的签名被改写为接收 6 个 `!hal.buffer_view`、返回 2 个 `!hal.buffer_view`。函数开头用 `hal.tensor.import` 把外部视图“导入”为不可变 Tensor，结尾用 `hal.tensor.export` 把计算结果 `%y` 和 `%s` “导出”回视图。这样既锁定了对外 ABI，又让函数体内部继续享受纯粹的 Tensor 值语义优化。

#### Stage 3: `preprocessing` —— 注入硬件目标靶向信息与自定义改写

* **当前痛点**：在切分 GPU 任务之前，编译器需要知道目标硬件的能力边界（比如目标后端是 Apple Metal GPU，其 Subgroup 大小是 32），同时留出插件扩展口（如算子替换、自定义量化或 Attention 匹配）。
* **核心决策**：执行 [buildPreprocessingPassPipeline](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FPreprocessing%2FPasses.cpp%23L97)，并将此前组装的设备目标信息（Device Assignment）挂载到模块顶层。
* **IR 演进本质**：模块顶部新增了 `#hal.device.target<"metal", ...>` 以及默认设备亲和性属性 `stream.affinity.default = #hal.device.affinity<@__device_0>`。这相当于给整张计算图贴上了“发往 Metal GPU 执行”的路由标签，后续阶段（如 Stage 9 选择 Subgroup 归约策略）将直接读取这里的硬件参数。

#### Stage 4: `global-optimization` —— 在切分任务前做最后一次全图大扫除

* **当前痛点**：一旦下一步把算子关进不同的 GPU Kernel（Dispatch Region），算子之间就隔了一堵“核函数调用墙”。如果图里还有冗余的 `Transpose`、`Reshape`、常量折叠或者可以提升（Hoisting）的操作，必须在切分任务前跨算子清理干净。
* **核心决策**：通过 [buildGlobalOptimizationPassPipeline](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FGlobalOptimization%2FPasses.cpp%23L91) 整理全图代数结构、消除冗余形状变换并规范化数据类型。
* **IR 演进本质**：在输入张量旁插入 `iree_tensor_ext.compute_barrier.start` 屏障，防止内部激进的 Reshape 穿透到外部 ABI 边界破坏输入签名，同时让计算图内部处于最紧致、最利于算子融合的形态。

### 模组二：任务切分与双轨分叉（Stages 5–6）

从这里开始，编译器做出第一个影响全局性能的重大决定：**哪些计算打包进同一个 GPU Kernel？Host 轨和 Device 轨如何分家？**

#### Stage 5: `dispatch-creation` —— 划定 GPU Kernel 的边界（算子融合）

* **当前痛点**：如果不做融合，第一层矩阵乘算完要写回显存，接着启动第二个 Kernel 读出结果加 `b1`，再启动第三个 Kernel 做 `ReLU`——显存带宽会被彻底打满。但也不能把整个模型塞进一个 Kernel，因为第二个矩阵乘需要等待第一个矩阵乘在 K 维上全部算完，且行归约的并行维度与矩阵乘完全不同。
* **核心决策**：[FormDispatchRegions.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FDispatchCreation%2FFormDispatchRegions.cpp%23L349) 以带归约性质的重计算算子（如 `matmul`、行 `reduction`）作为“锚点（Root）”，顺着全并行（All-parallel）的数据流向后吞并逐元素消费者（Consumer Fusion），划分出独立的 `dispatch.region`。
* **IR 演进本质**：残差 MLP 被精准切分为 **3 个设备任务（D0、D1、D2）**：

| 任务编号 | 融合锚点（Root） | 吞并的后处理算子 | 区域输入 | 区域输出 | 为什么在这里截断边界？ |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **D0** | 第一层 `linalg.matmul` | `+ b1`、`ReLU` | `X`, `W1`, `b1` | `H` (`16x64`) | 下一层 `H @ W2` 需要读取 `H` 的整行，无法逐元素流式传递，必须落盘为 `H`。 |
| **D1** | 第二层 `linalg.matmul` | `+ b2`、`+ R` | `H`, `W2`, `b2`, `R` | `Y` (`16x32`) | `Y` 既要作为模型最终输出返回，又要交给 D2 做行归约，必须作为独立边界输出。 |
| **D2** | 第三层行归约 `generic` | 无 | `Y` | `S` (`16`) | 独立的归约计算，每个输出元素汇总 `Y` 的一整行（32 列）。 |

#### Stage 6: `flow` —— Host 与 Device 正式分家（Outline 提取）

* **当前痛点**：在 Stage 5 中，虽然用大括号圈出了 3 个 `dispatch.region`，但它们依然嵌在主函数 `@main` 内部。编译器既没法把每个 Region 单独交给 GPU 后端去编译，也没法在主函数里清晰地分析任务间的内存调度。
* **核心决策**：[OutlineDispatchRegions.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FDialect%2FFlow%2FTransforms%2FOutlineDispatchRegions.cpp) 执行 **Outlining（函数外提）**，把每个区域的内部代码抽出来封装成顶层的 `flow.executable`，主函数里只留下轻量的符号调用 `flow.dispatch`。
* **IR 演进本质**：**编译管线在此处正式一分为二**：
  * **上方（Device 轨种子）**：生成 `@D0`、`@D1`、`@D2` 三个独立的 `flow.executable` 模块，内部装的是待编译的 `linalg` 算子（将在 Stages 8–10 中单独加工成 GPU 机器码）。
  * **下方（Host 轨主干）**：`@main` 函数变成了纯粹的任务编排流：`%h = flow.dispatch @D0(...)` ──► `%y = flow.dispatch @D1(%h, ...)` ──► `%s = flow.dispatch @D2(%y)`。

### 模组三：Host 轨资源与异步调度（Stage 7）

请注意：**Stage 7 只改写 Host 轨的 `@main` 函数，不碰 Device 轨内部的算术逻辑。**

#### Stage 7: `stream` —— 把虚拟张量变成物理内存区间与异步时间点

* **当前痛点**：在 `flow` 阶段，Host 轨还在假装传递虚拟的 Tensor（`%h`、`%y`、`%s`）。但在真实的 GPU 上，没有“返回 Tensor”这种硬件指令，只有“向某块显存地址写入多少字节”。编译器必须回答三个灵魂问题：
  1. `H`、`Y`、`S` 各自占多少字节？谁是临时的、谁要带出函数？
  2. 能不能把多个输出合并申请，减少调用操作系统/驱动分配器的次数？
  3. GPU 是异步执行的，CPU 怎么知道 D1 已经读完了 `H`、什么时候可以安全释放 `H` 的显存？
* **核心决策**：由 [ScheduleAllocation.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FDialect%2FStream%2FTransforms%2FScheduleAllocation.cpp%23L1638) 完成静态内存规划（Memory Planning）、缓冲区打包（Buffer Packing）和基于时间点（`!stream.timepoint`）的异步依赖链构建。
* **IR 演进本质**：
  * **精妙的内存生命周期分类与打包**：
    * **瞬态资源（`transient`，4096 字节）**：分配给 `H`（`16 × 64 × 4B = 4096B`）。它只在 D0 写入、D1 读取期间存活，一旦执行完毕立即通过 `stream.resource.dealloca` 释放。
    * **外部资源打包（`external`，2112 字节）**：`Y` 需要 `16 × 32 × 4B = 2048B`，`S` 需要 `16 × 4B = 64B`。因為它们都要返回给用户，Stream 阶段没有傻傻地申请两次内存，而是**一次性申请了一块 `2048 + 64 = 2112B` 的连续内存**！区间 `[0, 2048)` 放 `Y`，区间 `[2048, 2112)` 放 `S`，最后通过 `stream.resource.subview` 切出两个视图返回。
  * **显式字节切片与读写权限**：`stream.cmd.dispatch` 将所有参数改写为带偏移和长度的字节切片（如 `ro %arg6[%c0 for %c2048]` 表示只读访问输入 `X` 的 2048 字节，`wo %arg13[%c0 for %c4096]` 表示只写访问 `H` 的 4096 字节）。
  * **异步时间点（Timepoint）链条**：每次内存分配（`alloca`）、命令块执行（`cmd.execute`）、内存释放（`dealloca`）都会产生并消费 `!stream.timepoint`，像接力棒一样确保“内存分配好才启动 Kernel ──► Kernel 跑完才释放 `H` ──► 全部就绪才向用户返回 `Y` 和 `S`”。

### 模组四：Device 轨核函数生成（Stages 8–10）

现在，Host 轨已经在 Stage 7 规划好了内存布局（特别是 `Y` 和 `S` 共用一块 2112B 内存，`S` 从偏移 2048B 开始写）。接下来，编译器把注意力转回 **Device 轨的 `@D0`、`@D1`、`@D2` 三个核函数内部**，把它们从 `Linalg` 变成 GPU 硬件指令。

#### Stage 8: `executable-sources` —— 焊好 Host 与 Device 之间的指针插槽（ABI 契约）

* **当前痛点**：Host 轨按字节区间传参，而 Device 轨的 Kernel 需要知道：“我该从第几个寄存器插槽（Binding Ordinal）拿到输入指针？偏移量是多少？”
* **核心决策**：[MaterializeInterfaces.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FDialect%2FHAL%2FTransforms%2FMaterializeInterfaces.cpp%23L318) 将 `flow.executable` 转化为目标平台专属的 `hal.executable.variant`（此处为 `@metal_msl_fb`），并在核函数开头生成统一的 `hal.interface.binding.subspan` 接口指令。
* **IR 演进本质**：所有 Kernel 入口函数都变成了**无参函数 `func.func @entry()`**，内部不再有函数参数，而是通过 `binding(0)`、`binding(1)` 这样的插槽号去抓取内存子区间。最精彩的呼应出现在 D2 中：D2 的 `binding(0)`（读 `Y`）和 `binding(1)`（写 `S`）指向同一个底层资源，但写端显式携带了字节偏移 `2048`，与 Stage 7 的内存打包严丝合缝！

#### Stage 9: `executable-configurations` —— 拍板 GPU 并行策略（Tiling 与线程分工）

* **当前痛点**：面对 `D0`（`16×64` 矩阵乘，K=32）和 `D2`（`16×32` 行归约），GPU 有成百上千个线程，到底怎么分活？如果直接在 IR 上硬写循环拆分代码，策略逻辑和代码生成逻辑会彻底搅成一团。
* **核心决策**：在**不修改 Linalg 算子结构**的前提下，先由启发式配置器（[AppleConfig.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FCodegen%2FSPIRV%2FAppleConfig.cpp%23L22) 与 [KernelConfig.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FCodegen%2FSPIRV%2FKernelConfig.cpp%23L617)）分析 M/N/K 维度与硬件特性，把**分块方案（`lowering_config`）**和**翻译管线名称（`translation_info`）**作为属性标签贴在函数和算子上（即“先策划、后施工”）。
* **IR 演进本质**：编译器针对计算特征拍板了截然不同的两种 GPU 并行范式：

| 任务 | 选定的 Codegen 管线 | 工作组线程尺寸 (`workgroup_size`) | 分块配置 (`tile_sizes`) | 物理含义解读（极其关键！） |
| :--- | :--- | :--- | :--- | :--- |
| **D0** | `SPIRVBaseVectorize` | `[16, 16, 1]` (共 256 线程) | `[[16, 64], [1, 4], [0, 0, 4]]` | **输出数据并行 + 向量化**：1 个 Workgroup 承包全部 `16×64` 输出；每个线程负责算 `1行 × 4列`（恰好装进 1 个 `float4` 向量寄存器）；K 维（32）每次步进 `4`，循环 8 次累加完。 |
| **D1** | `SPIRVBaseVectorize` | `[8, 16, 1]` (共 128 线程) | `[[16, 32], [1, 4], [0, 0, 4]]` | **输出数据并行 + 向量化**：1 个 Workgroup 承包全部 `16×32` 输出；X 方向 8 个线程 × 每线程 4 列 = 覆盖 32 列；Y 方向 16 个线程覆盖 16 行。 |
| **D2** | `SPIRVSubgroupReduce` | `[32, 1, 1]` (共 32 线程) | `[[1], [0, 32]]` | **Subgroup 跨线程协作归约**：共发射 16 个 Workgroup（每组负责 1 行）；组内 32 个线程构成 1 个硬件 Subgroup，每人读 1 列，用硬件级 Shuffle 指令一把算出整行总和。 |

#### Stage 10: `executable-targets` —— 施工落地：生成向量指令、Subgroup 指令与 SPIR-V

* **当前痛点**：Stage 9 贴好了施工蓝图标签（Config），现在需要真正把高层 `linalg` 算子拆解成循环、分配到线程、打包成 `float4` 向量，并降级为 GPU 标准中间表示 SPIR-V。
* **核心决策**：调用 [SPIRV/Passes.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FCodegen%2FSPIRV%2FPasses.cpp%23L317) 中的对应管线，依次执行 Tile & Distribute ──► Vectorization（向量化） ──► Bufferization（张量转指针内存） ──► Lower to SPIR-V。
* **IR 演进本质**：
  * **在 D0 中（对应锚点 `H`）**：矩阵乘累加器变成了每个线程私有的寄存器向量 `vector<4xf32>`，K 维循环内转化为四条连续的硬件乘加指令 `spirv.GL.Fma`。更妙的是，原本紧跟在后面的 `+ b1` 和 `ReLU` 直接在寄存器里的 `vector<4xf32>` 上完成，最后才一次性写回 `H` 的显存——**全程没有为未加偏置的矩阵乘结果分配一分钱额外显存**！
  * **在 D2 中（对应锚点 `S`）**：生成了硬件级非均匀组归约指令 `spirv.GroupNonUniformFAdd <Subgroup> <Reduce>`，32 个线程在寄存器层面直接交换数据求和。

### 模组五：双轨汇合与运行时落地（Stages 11–12）

到这里，Host 轨停留在 Stage 7 的 `stream` 抽象命令，Device 轨停留在 Stage 10 的 `spirv.module`。最后两步将把两条轨道重新拧成一股绳，变成 CPU 可直接加载运行的二进制文件。

#### Stage 11: `hal` —— 双轨大汇合：录制硬件命令缓冲 + 序列化 GPU 着色器载荷

* **当前痛点**：`stream` 还是与具体驱动解耦的流式抽象，而 `spirv.module` 也还不是 Apple Metal 驱动能直接加载的着色器格式（MSL / Metallib）。
* **核心决策**：通过 [HAL/Transforms/Passes.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FDialect%2FHAL%2FTransforms%2FPasses.cpp%23L202) 将 Host 轨与 Device 轨同步降级到 **HAL（Hardware Abstraction Layer，硬件抽象层）**：
  * **Host 轨具体化**：
    * `stream.resource.alloca` ──► `hal.device.queue.alloca`（向设备队列申请物理 Buffer）。
    * `stream.timepoint` ──► `hal.fence`（硬件同步围栏）。
    * `stream.cmd.execute` ──► `hal.command_buffer`（命令缓冲区录制），任务之间的写后读依赖变成显式的 `hal.command_buffer.execution_barrier`。
    * **间接绑定表优化（Indirect Binding Table）**：由于每次调用 `@main` 时传入的权重和输入 Buffer 地址不同，但“先跑 D0、再跑 D1、最后跑 D2”的命令结构永远不变，IREE 将命令缓冲区设为可缓存复用，把 6 个输入、返回值存储（Slot 6）和临时存储 `H`（Slot 7）抽象为 8 个全局插槽（Slots 0–7），通过 `hal.device.queue.execute.indirect` 动态注入实际 Buffer。
  * **Device 轨序列化**：[MetalSPIRVTarget.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fplugins%2Ftarget%2FMetalSPIRV%2FMetalSPIRVTarget.cpp%23L110) 调用 SPIRV-Cross 把 `spirv.module` 翻译成 Apple Metal 源码（MSL），打包进 `hal.executable.binary`。如果你打开 D2 生成的 MSL 源码，会看到之前所有阶段的决策在最后一行代码上完美会师：

```cpp
// WorkGroupID.x 选定第几行，32 个线程通过 simd_sum（对应 Stage 9/10 的 SubgroupReduce）求和
float _32 = simd_sum((*spvDescriptorSet0._resource_var_0_0_)._m0[gl_LocalInvocationID.x + (gl_WorkGroupID.x * 32u)] + 0.0);
if (gl_LocalInvocationID.x == 0u) {
    // 只有第 0 号线程负责写回 S；这里的 + 512u 正好是 Stage 7 规划的 2048 字节偏移（2048 / 4 = 512 个 float）！
    (*spvDescriptorSet0._resource_var_0_1_)._m0[gl_WorkGroupID.x + 512u] = _32 + 0.0;
}
```

#### Stage 12: `vm` —— 把 Host 调度程序变成超轻量级字节码

* **当前痛点**：现在 GPU 代码已经打包成了二进制常量，但 Host 侧那堆 `hal.device.queue.alloca`、`hal.command_buffer.dispatch`、`hal.fence.await` 由谁来执行？如果直接编译成固定平台的 x86/ARM 机器码，模型文件就失去了跨平台可移植性；如果用庞大的 C++ 图解释器，又违背了 IREE 极简运行时的初衷。
* **核心决策**：通过 [VM/Transforms/Passes.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FDialect%2FVM%2FTransforms%2FPasses.cpp%23L77) 将 Host 侧代码全部降级为 **IREE VM（Virtual Machine）Dialect**：
  * GPU 的二进制内核被存放在只读数据段 `vm.rodata`。
  * 所有 HAL 硬件操作变成对外部 C 运行时模块（[runtime/src/iree/modules/hal/module.c](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fruntime%2Fsrc%2Firee%2Fmodules%2Fhal%2Fmodule.c%23L1061)）的系统调用声明 `vm.import @hal.*`（最终在 Metal 驱动层触发 [direct\_command\_buffer.m](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fruntime%2Fsrc%2Firee%2Fhal%2Fdrivers%2Fmetal%2Fdirect_command_buffer.m%23L936) 中的 `dispatchThreadgroups:`）。
  * 等待 GPU 完成的 `@hal.fence.await` 带有 `vm.yield` 属性，支持协程级异步挂起，避免 CPU 死等。
* **最终产物**：整個 `vm.module` 被序列化为 `.vmfb` 文件。IREE Runtime 只需要一个几百 KB 的字节码解释器 + 对应的 HAL Driver（Metal/Vulkan/CUDA），就能以零图解析开销跑起整个模型。

## 四、 核心机制深潜：读懂原文档“附读”背后的四个 MLIR 支柱

原文档末尾的“附读”塞入了大量零散的 MLIR 概念。要把它们真正消化并为你所用，只需提炼出支撑 IREE 运转的**四大底层支柱**：

### 1. 结构化计算抽象（Linalg 的三要素）
为什么 IREE 坚持要把算子转成 [Linalg Dialect](https://www.google.com/search?q=https%3A%2F%2Fmlir.llvm.org%2Fdocs%2FDialects%2FLinalg%2F)？因为 `linalg.generic` 用三个正交属性把“怎么访问数据”和“做什么算术”彻底解耦了：
* **`iterator_types`（迭代维性质）**：标明每个循环维是可独立并行的 `"parallel"`，还是需要跨步累加的 `"reduction"`。
* **`indexing_maps`（仿射映射投影）**：用数学投影描述访存关系。例如在 `(m, n)` 迭代空间中：
  * 输入 map 为 `(m, n) -> (n)`，意味着不管 `m` 怎么变都读同一个 `n`——这就是**广播（Broadcast）**的本质！
  * 输出 map 为 `(m, n) -> (m)`，意味着多个 `n` 迭代点写往同一个 `m`——这就是**归约（Reduction）**的本质！
* **`region payload`（标量计算体）**：剥离了所有形状和循环后，最内层纯粹的标量加减乘除（如 `arith.addf`、`arith.maximumf`）。
* **工程价值**：后续做算子融合（Tile & Fuse）时，编译器根本不需要管算子叫 ` BiasAdd` 还是 `ReLU`，只需对两个算子的 `indexing_maps` 做仿射求逆，就能精确算出“为了算出消费者的一块 `1×4` Tile，需要提前算出生产者的哪块切片”。

### 2. 目标传递风格（DPS）与 One-Shot Bufferization
在纯数学公式里，`C = A @ B` 凭空产生了一个新张量 `C`。但在硬件里，每次“凭空产生”都意味着昂贵的 `malloc`。
* **什么是 DPS（Destination Passing Style）**：Linalg 强制所有算子都显式传入一个 `outs(%dest)` 参数（见 [StableHLOToIREEInputDialects.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fplugins%2Finput%2FStableHLO%2FConversion%2FStableHLOToIREEInputDialects.cpp%23L513)）。在 Tensor 阶段，`%dest` 既为输出提供形状信息，又为 `matmul` 等归约算子提供累加初值（如 `linalg.fill` 填入的 0）。
* **如何转化为原地内存更新（In-place Bufferization）**：到了 Stage 10 的 [One-Shot Bufferization](https://www.google.com/search?q=https%3A%2F%2Fmlir.llvm.org%2Fdocs%2FBufferization%2F) 阶段，编译器会顺着 `ins` 和 `outs` 链条做读写冲突分析（Read-After-Write Analysis）。只要发现旧的 `%init` 在后面没人再读，就会直接把 Tensor 的 `outs(%init)` 变成对同一块物理内存的原位覆盖写入（In-place update），从而消除不必要的内存拷贝。

### 3. MLIR 方言转换三剑客（Target / TypeConverter / Pattern）
当你在比赛项目中编写或修改 Pass（尤其是 Stage 1 的前端转换或自定义算子接入）时，一定会遇到 [MLIR Dialect Conversion](https://www.google.com/search?q=https%3A%2F%2Fmlir.llvm.org%2Fdocs%2FDialectConversion%2F) 框架的三个核心组件：
* **`ConversionTarget`（合法性裁判）**：规定转换结束时哪些 Dialect/Op 是合法的（Legal）、哪些是非法的（Illegal）。注意：函数签名（`func.func`）、Region 块参数（Block Arguments）需要通过 `addDynamicallyLegalOp` 单独检查内部类型是否全部转换完毕。
* **`TypeConverter`（类型翻译官）**：定义类型映射规则（例如把非标准浮点或自定义张量转成标准类型，见 [ConvertPrimitiveType.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FInputConversion%2FCommon%2FConvertPrimitiveType.cpp%23L90)）。切记 MLIR 按**注册的逆序**匹配类型转换回调。
* **`OpConversionPattern` 与 `Adaptor`（施工队）**：在重写一个 Op 时，**读取原语义/属性用 `op.getFoo()`，获取已经转换好类型的新输入值必须用 `adaptor.getOperands()`**。如果转换中途两个阶段的类型暂时对不上，框架会插入临时的 `builtin.unrealized_conversion_cast` 桥接，最后由 `reconcile-unrealized-casts` 统一消解。

### 4. Canonicalization（规范化）与 Pattern Benefit（优先级）
* **[Canonicalization](https://www.google.com/search?q=https%3A%2F%2Fmlir.llvm.org%2Fdocs%2FCanonicalization%2F)（局部等价化简）**：利用贪心重写引擎（[Pattern Rewriter](https://www.google.com/search?q=https%3A%2F%2Fmlir.llvm.org%2Fdocs%2FPatternRewriter%2F)）消除死代码、折叠常量、合并连续的转置或形状变换，目标是“让 IR 更干净”。
* **Dialect Conversion（合法化降级）**：目标是“消灭所有 Illegal Op”。在 IREE 中，常常把高优先级的自定义 Canonicalization Pattern（例如赋予 `benefit = 1000` 或 `1024`）混入 Conversion 过程中，优先将特定算子组合化简成更高效的形态，防止被默认的通用降级规则拆碎。

