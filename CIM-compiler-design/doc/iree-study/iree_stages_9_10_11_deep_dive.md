# IREE 核心攻坚：Stage 9、10、11（Codegen 与 HAL 双轨合龙）深度剖析

在整个 IREE 的 12 个编译阶段中，**Stage 9（`executable-configurations`）、Stage 10（`executable-targets`）和 Stage 11（`hal`）** 是编译器技术密度最高、也是各类比赛与工程优化的核心深水区。

如果把前 8 个阶段比作“把食材洗净切好、摆上案板”，那么这 3 个阶段就是真正决定性能上限的“大厨掌勺与装盘出锅”：

* **Stage 9 是“总设计师画施工蓝图”**：在不改动算子结构的前提下，根据硬件特性与张量形状，拍板决定每个 GPU Kernel 采用什么并行策略、分块（Tile）切多大、分配多少个线程。

* **Stage 10 是“施工队按图施工”**：读取 Stage 9 的蓝图标签，把抽象的数学张量（Tensor）一步步拆解成多层循环、映射到物理线程坐标、打包进硬件向量寄存器（如 `float4`）或跨线程协作指令（如 Subgroup Shuffle），最终降级为 GPU 原生中间表示（SPIR-V / LLVM IR）。

* **Stage 11 是“Host 与 Device 双轨终极合龙”**：将 Device 轨产出的 SPIR-V 编译打包为目标硬件驱动可直接加载的二进制载荷（如 Metal MSL FlatBuffer），同时将 Host 轨的 `Stream` 抽象调度翻译成可缓存复用的硬件命令缓冲区（Command Buffer）、间接绑定表（Indirect Binding Table）与同步围栏（Fence）。

本文将继续沿用残差 MLP 案例中的三个核心任务（**D0 融合矩阵乘、D1 残差矩阵乘、D2 行归约**）与三个追踪锚点（**`H`、`Y`、`S`**），带你钻进这三个阶段的内部源码与 IR 演进细节。

## 一、 Stage 9：`executable-configurations` —— 策略与机制解耦的艺术

在进入 Stage 9 之前（即 Stage 8 `executable-sources` 结束时），Device 轨上的 `@D0`、`@D1`、`@D2` 内部装的仍然是高层的 [Linalg 算子](https://www.google.com/search?q=https%3A%2F%2Fmlir.llvm.org%2Fdocs%2FDialects%2FLinalg%2F)。此时编译器面临一个关键的软件工程抉择：**为什么不在遍历 Linalg 算子时直接动手拆循环、做向量化，而是非要单独设立一个 Stage 9，只往 IR 上贴属性标签？**

### 1. 为什么要做“策略（Policy）”与“机制（Mechanism）”的彻底解耦？

在早期的编译器设计中，启发式决策（比如“当 M=16, N=64 时每个线程算 4 个元素”）往往和循环改写代码写死在同一个 Pass 里。这会导致两个灾难性后果：

1. **牵一发而动全身**：一旦你想为新硬件微调分块大小，或者在比赛里针对某个特定 Shape 手写调优参数，就得去改极其复杂的循环变换 C++ 代码。

2. **丢失全局上下文**：一旦动手拆了第一个算子的循环，原本干净的 Linalg 迭代空间就被打碎成了 `scf.for`，后续算子很难再看清全貌。

因此，IREE 在 Stage 9 采用了“先策划、后施工”的架构（核心逻辑位于 [KernelConfig.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FCodegen%2FSPIRV%2FKernelConfig.cpp%23L617) 与特定硬件配置器如 [AppleConfig.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FCodegen%2FSPIRV%2FAppleConfig.cpp%23L22)）：

* **策略层（Stage 9 负责）**：读取 Stage 3 注入的硬件靶向参数（如 Apple GPU 的 Subgroup Size = 32、最大 Workgroup 内存、寄存器偏好）以及 Linalg 算子的静态维度（M/N/K），计算出最优参数，并以**两个标准属性**的形式挂载到 IR 上：

  * `#iree_codegen.translation_info`（贴在导出函数上）：指定接下来 Stage 10 要走哪条代码生成流水线（Pipeline），以及每个工作组的物理线程排布 `workgroup_size = [X, Y, Z]`。

  * `#iree_codegen.lowering_config`（贴在核心 Root 算子上）：指定多级循环分块的精确尺寸 `tile_sizes = [...]`。

* **机制层（Stage 10 负责）**：完全不关心当前是 Apple GPU 还是 NVIDIA GPU，只做个“无情的读表机器”——严格按照 `#iree_codegen.lowering_config` 上的数字切分循环、分配线程。

### 2. 逐位拆解 `lowering_config`：看懂二维嵌套数组里的每一个数字

许多人在打开 `9.executable-configurations.mlir` 时，看到像 `tile_sizes = [[16, 64], [1, 4], [0, 0, 4]]` 这样的嵌套数组会一头雾水：**为什么有 3 个子数组？为什么前两个只有 2 个数，第 3 个却有 3 个数且前面带两个 `0`？**

要读懂它，必须先回到 D0 中矩阵乘 `X(16×32) @ W1(32×64) -> H(16×64)` 的**三维迭代空间 `(M, N, K) = (16, 64, 32)`**：

* **第 0 维 `M`（范围 16）**：`"parallel"`（输出行并行维）。

* **第 1 维 `N`（范围 64）**：`"parallel"`（输出列并行维）。

* **第 2 维 `K`（范围 32）**：`"reduction"`（内积收缩归约维）。

在 `SPIRVBaseVectorize` 管线中，`tile_sizes` 的三个子数组分别对应 **GPU 硬件的三个拆解层级**，而每个子数组内部的位置严格对应 `(M, N, K)` 三个维度（填 `0` 或省略尾部的 `0` 代表“在当前层级不对该维度做切分”）：

| 分块层级 | D0 配置值 | 对应迭代维 `(M, N, K)` | 为什么这么设？（硬件映射与数学逻辑） | 
| ----- | ----- | ----- | ----- | 
| **第 0 层：Workgroup Tile**（工作组级分块） | `[16, 64]`（等价于 `[16, 64, 0]`） | `M = 16`, `N = 64`, `K = 不切分` | 决定 **1 个 GPU Workgroup（线程块）承包多大的输出块**。因为 `H` 总共只有 `16×64`，1 个 Workgroup 就能一口气包揽整张输出表！注意 `K` 维填 `0`（不跨 Workgroup 切分），因为同一个输出元素的 K 维累加必须在同一个 Workgroup 内部完成，否则会引发跨 Workgroup 的全局原子加或二次归约。 | 
| **第 1 层：Thread Tile**（单线程级分块） | `[1, 4]`（等价于 `[1, 4, 0]`） | `M = 1`, `N = 4`, `K = 不切分` | 决定 **Workgroup 内部的 1 个物理线程承包多少个输出元素**。这里让每个线程算 `1 行 × 4 列`（共 4 个连续的 `f32`）。为什么偏偏是 `4`？因为现代 GPU 的向量寄存器和内存事务天然对齐 128-bit（即 `4 × 32-bit float = float4`），选 `4` 可以直接触发最快的 `vector<4xf32>` 合并读写！ | 
| **第 2 层：Reduction Tile**（归约循环步长） | `[0, 0, 4]` | `M = 不切`, `N = 不切`, `K = 4` | 此时并行维 `M` 和 `N` 已经分配给了具体线程，因此前两位填 `0` 跳过；第 3 位 `K = 4` 表示**在每个线程内部求内积时，K 维（总长 32）每次循环步进 4 个元素**（共循环 `32 / 4 = 8` 次），每次循环内展开 4 条向量乘加（FMA）。 | 

弄懂了上面这张表，你就能瞬间推算出 D0、D1、D2 的 `workgroup_size` 是怎么算出来的：

* **推导 D0 的线程数 `[16, 16, 1]`**：

  * Workgroup 承包了 `M = 16` 行、`N = 64` 列；每个线程承包 `m = 1` 行、`n = 4` 列。

  * 在 GPU 编程习惯中，`threadIdx.x`（第 0 维）映射给连续访存的列维度 `N`，因此 X 方向需要 `64 / 4 = 16` 个线程；`threadIdx.y`（第 1 维）映射给行维度 `M`，因此 Y 方向需要 `16 / 1 = 16` 个线程。

  * 结论：`workgroup_size = [16, 16, 1]`（共 256 个线程）。

* **推导 D1 的线程数 `[8, 16, 1]`**：

  * D1 输出 `Y` 的形状是 `16×32`（`M = 16, N = 32`），每个线程依然算 `1 行 × 4 列`。

  * X 方向（列 `N`）只需要 `32 / 4 = 8` 个线程，Y 方向（行 `M`）需要 `16 / 1 = 16` 个线程。

  * 结论：`workgroup_size = [8, 16, 1]`（共 128 个线程）。

* **推导 D2（行归约）的配置 `[[1], [0, 32]]` 与线程数 `[32, 1, 1]`**：

  * D2 的迭代空间是二维 `(M = 16, N = 32)`，其中 `M` 是 `"parallel"`，`N` 是 `"reduction"`。

  * 在 [KernelConfig.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FCodegen%2FSPIRV%2FKernelConfig.cpp%23L617) 中，编译器发现归约维 `N = 32` 恰好等于 Stage 3 记录的 Apple Metal 硬件 `subgroup_size = 32`！

  * 于是编译器放棄了“单线程慢慢循环累加”的慢路径，果断切换到 **`SPIRVSubgroupReduce` 管线**：

    * 第 0 层 Workgroup Tile `[1]`（即 `[1, 0]`）：每个 Workgroup 只负责算 **`M = 1` 行**（总共 `16` 行就需要发射 `16` 个 Workgroup）。

    * 第 1 层 Subgroup/Thread Reduction Tile `[0, 32]`：跳过第 0 维 `M`，把第 1 维（`N = 32` 个待归约元素）直接摊派给同一个 Subgroup 里的 **`32` 个线程**（`workgroup_size = [32, 1, 1]`），每人读 1 个数，通过硬件级寄存器洗牌（Shuffle）一步求和！

### 3. Stage 9 末尾的隐藏动作：Generalize Named Ops（具名算子泛化）

如果你仔细对比 Stage 8 和 Stage 9 的 IR，会发现一个细节：Stage 8 里的 `linalg.fill` 和 `linalg.matmul` 到了 Stage 9 全部变成了带索引映射和标量计算体的 `linalg.generic`。

```
// Stage 9 输出的 D0 核心结构（贴上了 lowering_config，且 matmul 已泛化为 generic）
func.func @main_dispatch_0_matmul_16x64x32_f32()
  attributes {translation_info = #iree_codegen.translation_info<pipeline = SPIRVBaseVectorize workgroup_size = [16, 16, 1]>} {
  // ...
  %mm = linalg.generic {
    indexing_maps = [affine_map<(m, n, k) -> (m, k)>,
                     affine_map<(m, n, k) -> (k, n)>,
                     affine_map<(m, n, k) -> (m, n)>],
    iterator_types = ["parallel", "parallel", "reduction"]
  } ins(%x, %w1 : tensor<16x32xf32>, tensor<32x64xf32>) outs(%init : tensor<16x64xf32>)
    attrs = {lowering_config = #iree_codegen.lowering_config<tile_sizes = [[16, 64], [1, 4], [0, 0, 4]]>} {
  ^bb0(%in_x: f32, %in_w: f32, %acc: f32):
    %mul = arith.mulf %in_x, %in_w : f32
    %add = arith.addf %acc, %mul : f32
    linalg.yield %add : f32
  } -> tensor<16x64xf32>
  // 紧随其后的是加 bias 和 ReLU 的第二个 linalg.generic ...
}

```

**为什么要先用具名的 `linalg.matmul`，到了 Stage 9 拍板完配置后又把它打散成通用的 `linalg.generic`？**

* 在 Stage 9 拍板前，保留 `linalg.matmul` 这个名字可以让启发式配置器一眼认出“这是一个标准矩阵乘法”，从而快速套用针对矩阵乘调优过的分块公式。

* 一旦 `lowering_config` 标签贴好，使命就已经完成。此时把它泛化成 `linalg.generic`，后续 Stage 10 的分块、融合与向量化引擎就只需要处理 `linalg.generic` 这一种数据结构，极大简化了后端变换的实现复杂度。

## 二、 Stage 10：`executable-targets` —— 四步坍缩生成 GPU 原生指令

进入 Stage 10 后，编译器调用 [SPIRV/Passes.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FCodegen%2FSPIRV%2FPasses.cpp%23L317) 中注册的目标流水线（D0/D1 走 `addSPIRVBaseVectorizePassPipeline`，D2 走 `addSPIRVSubgroupReducePassPipeline`）。

很多初学者直接打开 `10.executable-targets.mlir` 看到满屏的 `spirv.AccessChain`、`spirv.GL.Fma` 会觉得跨度太大。实际上，在 Stage 9 到 Stage 10 之间，核函数内部经历了 **4 次井然有序的抽象坍缩**。我们以最复杂的 **D0（矩阵乘 + Bias + ReLU 融合产生 `H`）** 为例，慢镜头回放这 4 步：

### 第一步坍缩：Workgroup 级分块与融合（读取 `tile_sizes[0] = [16, 64]`）

编译器首先读取第 0 层分块配置 `[16, 64]`，将输出张量 `H` 按 `16×64` 切块，绑定到 GPU 的 `workgroup_id`（即 CUDA 中的 `blockIdx`）。

同时，一件至关重要的事情发生了——**Tile-and-Fuse（分块级消费者融合）**：

1. 原本 D0 里有两个算子：前面是算矩阵乘的 `generic_matmul`，后面是算 `+ b1` 和 `ReLU` 的 `generic_bias_relu`。

2. 当编译器按 `[16, 64]` 切分消费者 `generic_bias_relu` 时，顺着仿射映射求逆，把生产者 `generic_matmul` 以及最前面的 `linalg.fill`（清零）全部拉进了同一个 Workgroup 处理块内。

3. 更关键的是，编译器此时根据总尺寸 `(16, 64)` 除以 Workgroup Tile `(16, 64)`，把 Stage 5 留下的占位符 `iree_tensor_ext.dispatch.workgroup_count_from_slice` 具象化为常数 **`(1, 1, 1)`**（而 D2 因为总行数 16 除以 Workgroup Tile `[1]`，被具象化为 **`(16, 1, 1)`**）。这就决定了未来 Host 启动该 Kernel 时要发射多少个线程组！

### 第二步坍缩：Thread 级分块与 K 维循环拆分（读取 `tile_sizes[1] = [1, 4]` 与 `tile_sizes[2] = [0, 0, 4]`）

接下来在 Workgroup 内部，编译器读取第 1 层配置 `[1, 4]`，把 `16×64` 的工作量分发给 `16×16 = 256` 个物理线程：

* 线程的 `local_invocation_id.y`（范围 `0..15`）直接对应行坐标 `m = tid_y`。

* 线程的 `local_invocation_id.x`（范围 `0..15`）乘以 4 对应列起始坐标 `n = tid_x * 4`。

* 每个线程现在只负责算出 `H[tid_y, tid_x*4 : tid_x*4 + 4]` 这 **1 行 4 列**切片！

紧接着，编译器读取第 2 层归约配置 `[0, 0, 4]`，围绕矩阵乘建立起一个 `k` 从 `0` 到 `32`、步长为 `4` 的 `scf.for` 循环。此时单线程视角下的伪代码逻辑已经完全成型：

```
// 经过第二步坍缩后，单个 GPU 线程 (tid_x, tid_y) 的逻辑结构：
row = tid_y                       // 0..15
col = tid_x * 4                   // 0, 4, 8, ..., 60

// 1. 初始化 1x4 累加器切片为 0
acc_tile[1, 4] = fill(0.0)

// 2. K 维按步长 4 循环累加（共循环 32 / 4 = 8 次）
for k = 0 to 32 step 4:
  x_slice[1, 4]  =X[row, k : k+4]
  w1_slice[4, 4] = W1[k : k+4, col : col+4]
  acc_tile[1, 4] = matmul_micro_kernel(x_slice, w1_slice, acc_tile)

// 3. 出循环后，紧接着在同一块 1x4 切片上加 bias 并做 ReLU！
b1_slice[4]    = b1[col : col+4]
out_tile[1, 4] = max(acc_tile + b1_slice, 0.0)

// 4. 一次性写回全局输出 H
H[row, col : col+4] = out_tile

```

### 第三步坍缩：向量化（Vectorization）与 [One-Shot Bufferization](https://www.google.com/search?q=https%3A%2F%2Fmlir.llvm.org%2Fdocs%2FBufferization%2F)

看到上面伪代码里全是尺寸固定的 `[1, 4]` 和 `[4, 4]` 小切片了吗？这正是 Stage 9 精心挑选 `[1, 4]` 和 `[0, 0, 4]` 的伏笔！

1. **Linalg 转 Vector**：向量化 Pass 进场，将所有尺寸为 `[1, 4]` 的张量切片直接改写为硬件寄存器类型 **`vector<4xf32>`**：

   * `acc_tile` 变成常驻在线程私有寄存器里的 `%acc = arith.constant dense<0.0> : vector<4xf32>`。

   * 步长为 4 的 K 维微内核被展开（Unroll）为 **4 条连续的向量外积乘加指令 `vector.fma`**——每次取 `X` 的 1 个标量广播成 `vector<4xf32>`，与 `W1` 对应行的 `vector<4xf32>` 相乘并累加进 `%acc`。

   * K 循环结束后，`+ b1` 变成一条 `arith.addf %acc, %b1_vec : vector<4xf32>`，`ReLU` 变成一条 `arith.maximumf %biased, %zero_vec : vector<4xf32>`。

2. **One-Shot Bufferization（消除虚拟 Tensor，落地物理指针）**：

   * 此时再进行 Bufferization，编译器惊喜地发现：原本矩阵乘和 `bias/ReLU` 之间的中间张量 `%mm` 已经被彻底化简成了线程私有寄存器里的 `vector<4xf32>` 值传递！

   * 因此，**根本不需要为未加偏置的矩阵乘结果申请任何全局或共享内存**。整个 Kernel 只需要从 `binding(0)`、`binding(1)`、`binding(2)` 的物理指针（`memref`）读取 `X`、`W1`、`b1`，并在最后把算完 ReLU 的 `vector<4xf32>` 写入 `binding(3)`（即 `H` 的显存地址）。

### 第四步坍缩：降级到 SPIR-V（生成 `spirv.module`）

最后一步，编译器将 `memref` 寻址、`scf.for` 循环、`vector` 运算以及跨线程归约全部翻译为 Vulkan/Metal 通用的 **SPIR-V Dialect**。我们在 `10.executable-targets.mlir` 中就能看到 D0 和 D2 截然不同的底层硬件指令形态：

* **D0 核函数中的四连发向量 FMA（对应锚点 `H` 的寄存器内积）**：

  ```
  // 在 K 维步长为 4 的循环体内，连续展开 4 次 4 维向量乘加：
  // %18 是上一轮循环传下来的 vector<4xf32> 累加器；
  // %39, %42, %45, %48 是从 X[row, k..k+3] 读出并广播到 4 个分量的标量；
  // %28, %31, %34, %37 是从 W1[k..k+3, col..col+3] 连续读出的 4 行 float4 向量。
  %40 = spirv.GL.Fma %39, %28, %18 : vector<4xf32>
  %43 = spirv.GL.Fma %42, %31, %40 : vector<4xf32>
  %46 = spirv.GL.Fma %45, %34, %43 : vector<4xf32>
  %49 = spirv.GL.Fma %48, %37, %46 : vector<4xf32>
  
  ```

* **D2 核函数中的硬件 Subgroup 归约（对应锚点 `S` 的跨线程求和）**：

  ```
  // 每个线程从 Y[workgroup_id.x, local_invocation_id.x] 读出 1 个 f32 标量 %8
  %9  = spirv.FAdd %8, %cst_0_f32 : f32
  // 32 个线程在硬件 Subgroup 内部直接通过寄存器交换完成求和，无需经过 Shared Memory！
  %10 = spirv.GroupNonUniformFAdd <Subgroup> <Reduce> %9 : f32 -> f32
  %11 = spirv.FAdd %10, %cst_0_f32 : f32
  // 随后判断 if (local_invocation_id.x == 0)，仅由第 0 号线程将 %11 写入绑定插槽 1 的偏移 512 处
  
  ```

## 三、 Stage 11：`hal` —— Host 与 Device 的终极会师与运行时协议

当 Stage 10 结束时，我们来看一眼全局状态：

* **Device 轨**已经非常接近硬件了：三个 Kernel 都变成了 `spirv.module`。

* **Host 轨**却还停留在 Stage 7（`stream`）的状态：主函数 `@main` 里写的还是抽象的 `stream.resource.alloca`、`stream.cmd.execute` 和 `stream.timepoint.await`。

**Stage 11（`hal`，定义于 [HAL/Transforms/Passes.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fsrc%2Firee%2Fcompiler%2FDialect%2FHAL%2FTransforms%2FPasses.cpp%23L202)）的使命，就是让两条轨道在硬件抽象层（Hardware Abstraction Layer）完成总装合龙。** 这一阶段包含四个极高含金量的工程机制：

### 1. 读懂 Host 轨的“间接绑定表（Indirect Binding Table）”与命令缓冲复用

在 `11.hal.mlir` 的 `@main` 函数中，你会看到一段非常精巧的命令录制逻辑。为什么 IREE 不在每次用户调用 `@main` 时，直接把本次传入的 `X`、`W1` 等物理指针塞进 `hal.command_buffer.dispatch` 里，而是搞出了一套 **Slot 0 到 Slot 7 的间接绑定表**？

* **背后的硬件痛点**：在 Metal、Vulkan 或 DirectX 12 等现代显式图形/计算 API 中，录制一个 Command Buffer（命令缓冲区）需要做大量的驱动状态校验与描述符绑定，CPU 开銷不小。而对于同一个神经网络模型，无论你第 1 次调用还是第 10,000 次调用，**“先跑 D0 ──► 插屏障 ──► 再跑 D1 ──► 插屏障 ──► 最后跑 D2”的命令拓扑结构以及每个 Kernel 的线程组数量是 100% 固定不变的**！唯一变化的，只是每次调用传入的输入/输出 Buffer 内存地址。

* **IREE 的解决方案（Command Buffer Memoization + Indirect Bindings）**：
  编译器将不变的命令结构录制成可缓存复用的间接命令缓冲区，只留出 **8 个虚拟插槽（Global Binding Table Slots 0–7）**。在每次实际调用 `hal.device.queue.execute.indirect` 时，CPU 只需在最后关头把本次真实的 `!hal.buffer` 填入这 8 个插槽即可。

让我们把 **Host 全局插槽（Slots 0–7）**、**Stage 7 规划的物理资源** 与 **Stage 8 核函数内部看到的局部 `binding(N)`** 放在同一张表里，你会看到整套内存路由是多么严密：

| 全局绑定表插槽 (Host Slot) | 绑定的实际物理 Buffer (`!hal.buffer`) | 字节容量 | 在 D0 中的局部绑定号 | 在 D1 中的局部绑定号 | 在 D2 中的局部绑定号 | 
| ----- | ----- | ----- | ----- | ----- | ----- | 
| **Slot 0** | 模型输入 `X` (`input0`) | 2,048 B | `binding(0)` \[只读\] | 未使用 | 未使用 | 
| **Slot 1** | 模型输入 `W1` (`input1`) | 8,192 B | `binding(1)` \[只读\] | 未使用 | 未使用 | 
| **Slot 2** | 模型输入 `b1` (`input2`) | 256 B | `binding(2)` \[只读\] | 未使用 | 未使用 | 
| **Slot 3** | 模型输入 `W2` (`input3`) | 8,192 B | 未使用 | `binding(1)` \[只读\] | 未使用 | 
| **Slot 4** | 模型输入 `b2` (`input4`) | 128 B | 未使用 | `binding(2)` \[只读\] | 未使用 | 
| **Slot 5** | 模型输入 `R` (`input5`) | 2,048 B | 未使用 | `binding(3)` \[只读\] | 未使用 | 
| **Slot 6** | **打包返回值资源 (`Y` + `S`)** | **2,112 B** | 未使用 | `binding(4)` \[写 `0..2048`\] | `binding(0)` \[读 `0..2048`\] 与 `binding(1)` \[写 `2048..2112`\] | 
| **Slot 7** | **瞬态中间资源 `H`** | **4,096 B** | `binding(3)` \[写 `0..4096`\] | `binding(0)` \[读 `0..4096`\] | 未使用 | 

注意看 **Slot 6** 和 **Slot 7**：

* 在 D0 中，局部 `binding(3)` 被映射到全局 **Slot 7（`H`）** 写入数据；紧接着在 D1 中，局部 `binding(0)` 同样映射到全局 **Slot 7（`H`）** 读取数据——这就是跨 Kernel 数据传递在硬件层的真实面貌！

* 在 D2 中，局部 `binding(0)` 和 `binding(1)` **同时映射到全局 Slot 6（2112B 打包返回资源）**，一个从偏移 0 读 `Y`，一个往偏移 2048 写 `S`。

### 2. 区分两级硬件同步：`execution_barrier` 与 `hal.fence`

在 Stage 7 中，所有的依赖都用统一的 `!stream.timepoint` 表示；但到了 Stage 11 的 HAL 层，编译器将其精准拆分为**两种不同粒度的硬件同步原语**：

1. **核函数间的管线屏障（`hal.command_buffer.execution_barrier`）—— GPU 内部自同步**：

   * 在同一个 `hal.command_buffer` 内部，D0 写完 `H` 后 D1 要读 `H`；D1 写完 `Y` 后 D2 要读 `Y`。

   * 如果每次都让 GPU 停下来通知 CPU、再由 CPU 启动下一个 Kernel，往返延迟会高达数十微秒。

   * 因此，编译器将 D0、D1、D2 录制在**同一个 Command Buffer** 里，仅在 D0 与 D1 之间、D1 与 D2 之间各插入一条轻量级的 `hal.command_buffer.execution_barrier`。GPU 硬件命令处理器（Command Processor）在芯片内部刷新缓存并等待前序着色器写回完成，全程零 CPU 干预。

2. **队列级异步围栏（`!hal.fence`）—— Host 与 Device 跨设备同步**：

   * 在 Command Buffer 外部，当涉及**向队列申请显存（`hal.device.queue.alloca`）**、提交整个命令缓冲（`hal.device.queue.execute.indirect`）**以及**安全回收 `H` 的显存（`hal.device.queue.dealloca`）时，必须使用 `!hal.fence`。

   * 完整的 Fence 接力链条为：

     ```
     queue.alloca(2112B) ──► fence_alloc_0 ┐
                                           ├──► fence.join ──► [等待分配完成]
     queue.alloca(4096B) ──► fence_alloc_1 ┘                        │
                                                                    ▼
                                               queue.execute.indirect (跑 D0->D1->D2)
                                                                    │
                                                                    ▼ 产生 fence_exec_done
                                               queue.dealloca(H, wait = fence_exec_done)
                                                                    │
                                                                    ▼ 产生 fence_all_done
                                               hal.fence.await(fence_all_done) ──► 切分 Buffer Views 返回用户
     
     ```

### 3. Device 轨二进制序列化：从 `spirv.module` 到 Metal MSL 的终极印证

在 Host 轨生成 HAL 命令的同时，Stage 11 调用目标后端插件 [MetalSPIRVTarget.cpp](https://www.google.com/search?q=https%3A%2F%2Fgithub.com%2Firee-org%2Firee%2Fblob%2Fe4a3b0405d7d23554da26403658d0e8c3c5ecf25%2Fcompiler%2Fplugins%2Ftarget%2FMetalSPIRV%2FMetalSPIRVTarget.cpp%23L110) 处理 Device 轨的三个 `hal.executable`：

1. 将 Stage 10 生成的 `spirv.module` 序列化为标准 SPIR-V 二进制字节流。

2. 调用内置的 **SPIRV-Cross** 编译器，将 SPIR-V 交叉编译为 Apple 平台原生的 **Metal Shading Language (MSL)** 源码文本（若开启 `--iree-metal-compile-to-metallib=true` 则进一步调用 Xcode 工具链编译为二进制 `.metallib`）。

3. 将 MSL 源码、入口函数名、线程组尺寸 `[X, Y, Z]` 以及绑定权限标志一起打包序列化为 FlatBuffer，存入 `hal.executable.binary`（随后在 Stage 12 变成 `vm.rodata` 常量字节数组）。

现在，让我们打开 Stage 11 为 D2（行归约）生成的最终 Metal 着色器源码，把前面横跨 Stage 7、8、9、10、11 的所有线索一次性串联起来：

```
// Stage 11 最终产出的 Apple Metal 核函数源码（节选核心计算部分）
kernel void main_dispatch_2_generic_16x32_f32(
    device _type_0& _resource_var_0_0_ [[buffer(0)]],   // 对应 Stage 8 的 binding(0) -> Stage 11 的 Slot 6 (读 Y)
    device _type_0& _resource_var_0_1_ [[buffer(1)]],   // 对应 Stage 8 的 binding(1) -> Stage 11 的 Slot 6 (写 S)
    uint3 gl_WorkGroupID [[threadgroup_position_in_grid]],
    uint3 gl_LocalInvocationID [[thread_position_in_threadgroup]])
{
    // 1. gl_WorkGroupID.x (0..15) 对应 Stage 9 的 Workgroup Tile [1]（共 16 个工作组，每组算 1 行）
    // 2. gl_LocalInvocationID.x (0..31) 对应 Stage 9 的 Thread Tile [0, 32]（组内 32 个线程各读 1 列）
    // 3. simd_sum(...) 对应 Stage 10 的 spirv.GroupNonUniformFAdd <Subgroup> <Reduce>
    float _32 = simd_sum(
        _resource_var_0_0_._m0[gl_LocalInvocationID.x + (gl_WorkGroupID.x * 32u)] + 0.0
    );

    // 4. 仅由组内第 0 号线程负责将整行归约结果写回显存
    if (gl_LocalInvocationID.x == 0u)
    {
        // 5. 为什么下标要 + 512u？！
        // 因为 Stage 7 把 Y(2048B) 和 S(64B) 打包进了同一块 2112B 的返回内存中（Slot 6）！
        // Stage 8 在 binding(1) 上记录了 byte_offset = 2048；
        // Stage 10 在转化为 f32 数组寻址时，将 2048 字节除以 sizeof(float)=4，得到了精确的元素偏移 512u！
        _resource_var_0_1_._m0[gl_WorkGroupID.x + 512u] = _32 + 0.0;
    }
}

```

看到那个 `+ 512u` 和 `simd_sum` 了吗？很多人在看 IREE 源码时觉得 Host 侧的 `Stream/HAL` 和 Device 侧的 `Codegen/SPIRV` 各写各的、互不相干；但当你顺着 `2048 字节偏移 ──► subspan offset ──► + 512u` 这条线一路追到底层 Metal 代码时，就能真正体会到 IREE 全栈协同编译的威力。

