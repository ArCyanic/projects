// 第 3 章 详细设计与实现

= 详细设计与实现
<ch3-详细设计与实现>

== 存算方言体系设计
<sec3-1-存算方言体系设计>

=== 核心算子语义建模
<sec3-1-1-核心算子语义建模>

MLIR 的 `linalg` 方言用索引映射、迭代器和标量 region 表达结构化计算，支持 tensor 与 buffer 形式，并可下降到不同硬件。CIM 方言进一步表达目标设备的部署与执行操作：`cim.array.load` 写入常驻权重，`cim.mvm` 保留可重组的矩阵关系，`cim.bit` 与 `cim.elt` 完成逐位点积和整数结果重建。

在方言设计原则上，`cim` 方言全面遵循*目标传递风格*（Destination-Passing Style），将所有计算的输出缓冲区作为显式操作数绑定；同时通过 TableGen ODS 中的 `SideEffectInterfaces` 严格标注每个操作数的读写副作用（`MemReadAt<0, FullEffect>` 与 `MemWriteAt<0, FullEffect>`），为下游的死代码消除、活跃区间分析与缓冲区复用提供精准的依赖图依据。@tbl-cim-dialect-ops 详细列出了 `cim` 方言的核心算子集合及其语义。

#figure(
  align(center)[#table(
    columns: (20%, 30%, 50%),
    align: (x, y) => if y == 0 { center + horizon } else { (center + horizon, left + horizon, left + horizon).at(x) },
    table.header([算子标识符], [操作数格式与类型], [物理语义与设计约束],),
    table.hline(),
    [`cim.array.load`], [`ins(src: memref<KxN, i8>)`\ `outs(dst: memref<KxN, i8, #cim.memory_space<array>>)`], [部署阶段将静态权重写入存算阵列，仅在初始化函数 `__cim_array_init` 中合法出现],
    [`cim.mvm`], [`ins(src: memref<1xK, i8/i32>, weight: memref<KxN, i8>)`\ `outs(dst: memref<1xN, i32>)`], [逻辑层级矩阵向量乘，覆盖写输出；出现在缓冲化之后、阵列坐标绑定之前，供链接后的权重拼接与复制改写],
    [`cim.bit`], [`ins(src, weight)`\ `outs(dst: memref<1xN, i32>) {index = i}`], [物理层级单比特 MVM，驱动阵列执行第 $i$ 个二进制位的存内点积，由位展开 Pass 产生],
    [`cim.elt`], [`{add|sub|mul|div} {vv|vi}`\ `ins(src1[, src2]) outs(dst) [{immediate = imm}]`], [片上向量 ALU 计算，支持向量-向量（vv）与向量-立即数（vi）模式，承载移位、累加与偏置加法],
    [`memref.copy`], [`%src, %dst : src-type to dst-type`], [原生 MemRef 操作，统一承载 SRAM 间拷贝、常量导入及 HAL 边界导入导出],
  )],
  caption: [CIM 计算算子与原生搬运操作],
  kind: table,
) <tbl-cim-dialect-ops>

Array global 使用 `#cim.memory_space<array>`，物理切片由原生 `memref.subview` 表达。
SRAM 直接由 entry-local `memref.alloc` 根及其派生视图表示，保持默认 memory space。
HAL binding、普通常量 global 与 Array global 各自保留原生来源。

=== 多级 IR 渐进降级模型
<sec3-1-2-多级-ir-渐进降级模型>

存算一体编译体系横跨高层图优化、中层循环分块与底层物理时空调度。本项目构建了分层的*渐进式降级*（Progressive Lowering）管线，将高层神经网络模型划分为四个语义清晰的 IR 演进阶段，如 @fig-cim-ir-pass-isa-mapping 所示。

#figure(
  image("assets/cim-ir-pass-isa-mapping.pdf", width: 100%, alt: "从结构化 IR 到底层物理 ISA 的多级降级流水线与 Pass 映射"),
  caption: [从结构化 IR 到底层物理 ISA 的多级降级流水线与 Pass 映射],
) <fig-cim-ir-pass-isa-mapping>

降级流水线在时间轴上划分为四个连续演进的抽象层次。在最顶层的结构化张量 IR 阶段，计算以不可变张量 SSA 为载体，通过 `linalg.matmul` 与 `linalg.generic` 表达高层矩阵收缩与逐元素变换，并在 Dispatch 形成之前完成跨分支异构块对角融合。进入逻辑 CIM IR 阶段后，经过工作组划分与内存缓冲化，高层张量算子降级为绑定显式 MemRef 缓冲区的 `cim.mvm` 与 `cim.elt`，此时权重矩阵仍保持逻辑规约形状，为链接后的横向拼接与权重复制保留改写空间。

在 HAL 链接阶段，编译器将逻辑表示降级为物理 CIM IR，完成静态权重在全局单阵列中的物理坐标绑定与 SRAM 活跃期分配，在初始化入口生成常驻写入指令 `cim.array.load`，同时驱动位串行展开 Pass 将单个 `cim.mvm` 裂变为多轮单比特存内点积 `cim.bit` 与片上 `cim.elt` 移位累加控制流。最终在物理 ISA 阶段，编译器将所有物理视图转换为平坦的 64 字节对齐 SRAM 绝对地址与阵列位列偏移，生成符合硬件规范的文本 ISA 指令集，并封装为标准的 `hal.executable.binary` 二进制载荷嵌入 VMFB 模块中。

逻辑 MVM 固定为 `[1,K] × [K,N] → [1,N]xi32`，覆盖写目标；K 分块的部分和由显式 Elt add 累加。
物理化后，原生无参数入口保留 HAL binding/workgroup 操作，动态缓冲区成为 SRAM arena 的 views，
静态权重成为固定 Array views。Serializer 从这份物理 IR 同时投影 payload 与 ISA；二者不互相回读。

== 全局计算图优化
<sec3-2-全局计算图优化>

=== 前端算子规范化
<sec3-2-1-前端算子规范化>

赛题线性层主要由 `MatMulInteger` 和 `Gemm` 表达，权重采用 `[N,K]` 布局。
`CIMNormalizeONNXLinearPass` 使用原生 `torch_c` tensor materialization，统一生成 i32 累加的
`linalg.matmul`；RHS 转置由 `(m,n,k) → (n,k)` 的 indexing map 表达，bias 交给原生 ONNX Add 转换。
i8/i32 激活与 i8 权重共用这条路径，不再生成需要单独截断规范化的 i64 accumulator。
自有 Gemm 重写要求 `transA=0, alpha=1, beta=1`；显式 `transB=1` 的 i8 Gemm 沿用已验证的上游转换。

=== DAG 块对角融合
<sec3-2-2-dag-块对角融合>

单物理存算阵列的高效利用依赖于在全局视角下对多个离散 MVM 算子进行空间重组与合并执行。在传统的串行调度中，若两个并行的分支层分别执行形状为 $[1, K_1] times [K_1, N_1]$ 与 $[1, K_2] times [K_2, N_2]$ 的矩阵乘，硬件需依次发起两次阵列计算，占用 $ceil(N_1 / 512) + ceil(N_2 / 512)$ 个执行窗口。当各个子算子的输出列宽 $N_i$ 较小（例如 $N_1=64, N_2=128$）时，阵列的列利用率极低，导致多轮位串行计算产生严重的执行时延浪费。

为突破这一瓶颈，编译器在 IREE preprocessing 中实现了基于 DAG 依赖切片的*异构块对角融合机制*（Heterogeneous Block-Diagonal Fusion），并在 `CIMFuseHeterogeneousContractionsPass` 中予以实现。该算法首先通过 `mlir::getBackwardSlice` 为同一基本块内的所有候选收缩算子构建后向依赖切片，严格判定算子间的无环独立性：当且仅当算子 $A$ 与算子 $B$ 满足 $A in.not "BackwardSlice"(B)$ 且 $B in.not "BackwardSlice"(A)$ 时，二者才被判定为可融合候选。在满足批量维度 $M$ 与数据类型兼容的前提下，算法评估融合带来的窗口节约收益 $Delta W = ceil(N_1 / 512) + ceil(N_2 / 512) - ceil((N_1 + N_2) / 512)$，并将候选组重组为统一的块对角权重矩阵：

$ W_("fused") = mat(W_1, bold(0)_(K_1 times N_2); bold(0)_(K_2 times N_1), W_2) in bb(Z)^((K_1 + K_2) times (N_1 + N_2)) . $ <eq-block-diagonal-weight>

相应地，两路输入激活沿 K 维拼接为 $x_("fused") = [x_1, x_2] in bb(Z)^(1 times (K_1 + K_2))$。单次执行 $z_("fused") = x_("fused") W_("fused")$ 原位生成拼接结果 $[x_1 W_1, x_2 W_2]$，随后通过 `tensor.extract_slice` 零拷贝分发给各自的下游消费者。

@fig-weight-optimization-primitives 概括了编译器支持的三项核心权重重排与优化原语。

#figure(
  image("assets/weight-optimization-primitives.pdf", width: 100%, alt: "三大权重排布优化原语：横向列拼接、异构块对角融合与多行权重复用"),
  caption: [三大权重排布优化原语：横向列拼接、异构块对角融合与多行权重复用],
) <fig-weight-optimization-primitives>

除异构块对角融合外，系统还支持*横向列拼接*（Horizontal Packing）与*多行权重复用*（Weight Replication），二者发生在 HAL 链接之后，作用对象是已经缓冲化的 `cim.mvm`。

在同一个标准 preprocessing hook 中，异构融合之后调用 IREE 原生 `FuseHorizontalContractions`。
它保留 $M<16$ 不融合的限制，随后原生 dispatch formation 消费共享激活的收缩结构。
Buffer-level conversion 同时检查 Linalg `cast` 属性与 scalar body，并要求 activation/output maps
分别为 `(m,k)` 与 `(m,n)`，避免 unsigned 或转置 activation 在改写中丢失语义。

链接后的 `cim-pack-horizontal-mvms` 将同一 Dispatch 内共享激活的权重沿输出列拼成 $[K, sum N_i]$。若各 MVM 的目的视图在列上连续，直接合并该视图；否则先写入临时宽缓冲，再以 `memref.copy` 把各列块写回原来的目的缓冲。拷贝使拼接结果与原缓冲同时存活，因此拼接后 SRAM 峰值上升，由后续活跃期复用回收。对于输入高度 $K$ 较小且阵列行资源充裕的算子，`cim-replicate-weight-mvms` 在行维复制静态权重，使多行激活在同一窗口内并发驱动不同行区间。

为了防止图级或链接后的权重重组超出唯一的 $1024 times 512$ 物理阵列，编译器设计了*静态试排保护机制*（Dry-Run Placement Guard）。在块对角融合、横向拼接或权重复制生效前，优化器调用 `planStaticArray` 模拟二维放置。试排失败则保持未改写 IR。

== 结构化平铺融合
<sec3-3-结构化平铺融合>

=== 阵列两级平铺策略
<sec3-3-1-阵列两级平铺策略>

高层神经网络中的线性层形状具有高度的多样性，往往超出单次存算阵列执行的物理边界（$1024$ 行与 $512$ 逻辑列）。为了将任意维度的矩阵收缩计算规范化降级为硬件支持的离散 MVM 窗口，编译器在 Dispatch 内部设计了*两级平铺策略*（Two-Level Tiling Strategy），并在 `CIMSelectLoweringStrategyPass` 中为目标算子附着 IREE 原生 `lowering_config` 编译配置。

两级平铺在空间与时间维度分别求解不同的调度抽象。在第一层*工作组级平铺*（Level 0: Workgroup Grid）中，编译器面向批量激活维度 $M$，求解分块参数 $m_("tile") = "uniformTileSize"(M, M_("cap"))$，将多批次激活切分为由 IREE 运行时直接调度的独立 Dispatch 任务网格；在第二层*阵列级平铺*（Level 1: Array Tile）中，编译器面向存算硬件的物理几何边界，求解矩阵归约轴 $K$ 与输出通道轴 $N$ 的刚性分块。对于任意逻辑收缩算子，其阵列分块尺寸推导为：

$ k_("tile") = "uniformTileSize"(K, 1024), wide n_("tile") = "uniformTileSize"(N, 512) . $ <eq-tiling-sizes>

为了消除循环边界处因尺寸无法整除而引入的动态掩码判定与条件分支开销，算法实现了均匀整除函数 $"uniformTileSize"(S, C)$。该函数首先计算最小切分数 $T = ceil(S / C)$，随后递增搜索满足 $(S "mod" T) = 0$ 的最小整数，最终返回 $S / T$ 作为平铺步长。这一设计保证了任意算子切分出的所有子块在几何尺寸上完全恒定，保证当前路径使用尺寸一致的合法矩形。

=== 逐元素算子片上原位融合
<sec3-3-2-逐元素算子片上原位融合>

在确立两级平铺配置后，编译器在 `CIMLegalizeArrayTilesPass` 中借助 MLIR 原生 `TilingInterface` 驱动分块循环降级与算子融合，构建高效的片上数据流动拓扑。

针对外层并行维度（批量 $M$ 与输出通道 $N$），Pass 首先调用 `tileConsumerAndFuseProducersUsingSCF` 生成外层平铺循环，将输入张量切片与矩阵乘生产者一并纳入循环作用域。随后，编译器通过 `fuseElementwiseConsumers` 深度遍历循环外部的数据流依赖，识别依附于当前 MVM 输出的受支持的整数逐元素 `linalg.generic` 算子，并调用 `scf::tileAndFuseConsumer` 将其直接*原位融合*（In-Place Fusion）至输出通道 $N$ 的平铺循环体内部。该机制使 MVM 输出的高精度中间点积直接在片上 SRAM 局部视图中被消费，让这些中间结果继续沿任务内视图传递。

对于归约维度超出阵列行容量（$K > 1024$）的大矩阵，编译器进一步调用 `scf::tileUsingSCF` 在并行循环内部生成串行 `scf.for` 归约循环。在每个内层归约步长中，硬件驱动对应物理行切片执行单次存内计算，并在编译器预先分配的局部 SRAM 累加器中原位完成部分和（Partial Sums）累加。全部归约迭代完成后，累加器内的完整结果原位传递给已融合的下游逐元素算子，实现了高内聚的片上链式计算流水线。

== 物理映射代码生成
<sec3-4-物理映射代码生成>

=== 单阵列全局静态放置
<sec3-4-1-单阵列全局静态放置>

目标存算芯片仅集成单一固定的 $1024 times 512$ 物理阵列，且硬件不支持运行期权重的动态重载或分页换入。为了确保全模型所有常驻权重在唯一的物理阵列中合法共存，编译器在 HAL 链接阶段通过 `CIMLinkExecutablesPass` 汇聚全部 Dispatch 的静态权重，并驱动 `StaticArrayPlacement` 求解全局二维空间放置。

算法在设计上实现了逻辑引用与物理区域的完全解耦。编译器将全模型权重抽象为两级结构：第一级为全局唯一的物理区域集合 `regions`，相同内容与几何尺寸的静态权重被自动归并至同一区域索引，实现了常驻权重的天然去重；第二级为各算子的逻辑使用切片 `uses`，精确记录各层计算对物理区域内部子块的几何映射关系。

放置按面积、高度、宽度和内容的确定性次序处理矩形。候选行是 0 及已放置矩形的下边界；
每行从列 0 开始按列顺序越过重叠 blocker，找到该行第一个可容纳的最左空位。所有 region 必须同时
位于阵列内且互不重叠；结构零也属于常驻面积。优化试探与最终部署共用这个 planner。

物理坐标确定后，编译器在模块中生成全局唯一的初始化函数 `__cim_array_init`，为每个物理区域插入一条 `cim.array.load` 指令，负责在系统启动时将主机侧常量数据一次性写入 `@cim_array` 符号对应的物理切片中。

=== 活跃期 SRAM 内存分配
<sec3-4-2-活跃期-sram-内存分配>

芯片片上 SRAM 仅有 512 KiB 容量，承载着输入激活、输出张量、常量偏置以及位展开过程中的高频暂存区（Scratchpad）。此外，底层硬件 DMA 与向量 ALU 强制要求所有物理内存缓冲区的起始地址满足 64 字节硬件对齐约束。若采用传统的顺序累加分配策略，多层网络累积的中间张量将迅速耗尽 SRAM 空间。

SRAM materializer 先将边界数据与常量变成紧凑 staging allocations。省略 import 需要证明
每次读取及最终整块 export 都已被前序完整写入覆盖；LLVM `BitVector` 合并连续静态区间。
权重读取、初始化覆盖与序列化共用真实 view-chain 地址归约，支持 cast 放宽类型 offset 后的地址追溯。

位串行展开补齐 scratch 后，`CIMAllocateSRAMPass` 为静态 entry allocations 设置 64 B 对齐并插入
作用域末尾的 dealloc。Reuse 模式运行 MLIR `OptimizeAllocationLiveness`，按全部 alias 的最后使用
移动释放点；随后 `StaticMemoryPlannerAnalysis` 以 BestFit 或 Trivial 算法计算偏移，并完成 arena/view
改写。CIM 只检查最终 arena 是否超过 512 KiB，不另建 liveness 状态机或冲突图。

=== 位串行指令生成
<sec3-4-3-位串行指令生成>

在完成全局权重放置与 SRAM staging、但尚未分配最终地址时，编译器进入底层的位串行展开与指令降级阶段。在 `CIMExpandBitSerialPass` 中，编译器遍历所有逻辑 `cim.mvm` 算子，根据输入激活的数据位宽 $B$（如 8 位有符号整型），将其精确裂变为 $B$ 轮硬件支持的原生点积操作：

首先，Pass 发起第 0 位的单比特存内点积 `cim.bit {index = 0}`，直接覆盖写入输出累加器；对于中间位 $1 lt.eq i lt.eq B-2$，Pass 驱动硬件执行对应位的存内点积并将结果写入复用的片上 Scratch 暂存区，随后通过片上向量算子 `cim.elt <mul> <vi>`（携带立即数 $2^i$）完成左移，并通过 `cim.elt <add> <vv>` 累加至输出缓冲区；对于最高符号位（$i = B-1$），点积结果在左移 $2^(B-1)$ 后通过 `cim.elt <sub> <vv>` 从累加器中减去，完成*补码极性修正*。这一机制在 IR 层面精确重建了补码算术逻辑，消除了任何运行期额外的标量控制开销。

最终，编译器通过目标代码转换通道将物理 CIM IR 降级为符合硬件执行规范的 ISA 指令流。所有的 MemRef 抽象被平坦化为绝对 SRAM 地址偏移量与阵列物理行列坐标，生成文本格式的汇编指令序列，并通过 IREE 的 HAL 框架打包为专有的 `hal.executable.binary` 二进制载荷，嵌入交付的 VMFB 可执行文件中。


