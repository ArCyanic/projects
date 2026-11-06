// 第 2 章 工作原理、关键技术原理与结构设计

= 工作原理、关键技术原理与结构设计
<ch2-工作原理与架构设计>

== 目标硬件执行模型
<sec2-1-目标硬件执行模型>

目标存算一体芯片采用由二维物理存算阵列（CIM Array）与片上静态随机存取存储器（SRAM）构成的非对称存储-计算架构。存算阵列专门用于在模型部署阶段灌注并固化静态权重参数；片上 SRAM 则作为统一的线性数据空间，承载宿主输入的激活张量、各层输出结果以及计算过程中的临时数据（Scratchpad）。在物理层级，存算阵列包含 1024 条行控制线与 4096 条物理位列线。对于 `i8` 权重，硬件将每 8 个相邻的物理位列在逻辑上解释为一个权重单元列，从而向编译器呈现出 $1024 times 512$ 的规则二维逻辑视图。@tbl-hardware-specs 汇总了硬件资源的主要规格及其对编译器的硬性约束。

#figure(
  align(center)[#table(
    columns: (22%, 36%, 42%),
    align: (x, y) => if y == 0 { center + horizon } else { (center + horizon, center + horizon, left + horizon).at(x) },
    table.header([硬件资源], [物理规格], [编译约束与含义],),
    table.hline(),
    [存算阵列], [1 个，1024 行 $times$ 4096 位列], [全模型静态权重共用 $1024 times 512$ 个 `i8` 单元],
    [单次 MVM 窗口], [矩形区域 $[K, N]$], [单次物理执行须满足 $K lt.eq 1024, N lt.eq 512$],
    [片上 SRAM], [524,288 字节 (512 KiB)], [输入、输出与中间暂存共享统一线性地址空间],
    [SRAM 寻址], [64 字节硬件对齐], [所有物理缓冲区起始地址必须满足 64 字节整倍数],
    [权重生命周期], [部署期一次性写入], [推理期权重物理常驻，不支持动态换页],
  )],
  caption: [目标存算一体硬件资源及编译约束],
  kind: table,
) <tbl-hardware-specs>

在矩阵向量乘（MVM）映射模型中，权重的输入归约轴（$K$ 维）映射至阵列行控制线，输出通道轴（$N$ 维）映射至阵列位列线。对于单层线性计算，设输入行向量为 $x in bb(Z)^(1 times K)$，权重矩阵为 $W in bb(Z)^(K times N)$，偏置向量为 $b in bb(Z)^(1 times N)$，其数学语义为 $z = x W, y = z + b$。硬件无法在单周期内直接输入多位宽有符号整型激活值，而是采用二进制补码逐位驱动的位串行计算机制。对于 $B$ 位有符号整型激活值 $x$（$B$ 为 8 或 32），其补码展开为：

$ x = sum_(i=0)^(B-2) "bit"_i (x) 2^i - "bit"_(B-1) (x) 2^(B-1) . $ <eq-bit-serial-expansion>

式中 $"bit"_i (x) in {0, 1}$ 为激活值 $x$ 的第 $i$ 个二进制位。由矩阵乘法的线性性质，单次 MVM 在时间轴上解构为 $B$ 轮单比特存内点积计算与片上移位累加：

$ z = sum_(i=0)^(B-2) 2^i ( "bit"_i (x) W ) - 2^(B-1) ( "bit"_(B-1) (x) W ) . $ <eq-bit-serial-recon>

每一轮存内计算产生一个 `i32` 格式的中间点积向量。在片上控制流中，第 0 位结果直接写入累加器基底；第 $1 lt.eq i lt.eq B-2$ 轮结果在 SRAM 中左移 $i$ 位后累加至结果向量；最高符号位（$i=B-1$）在左移后从累加器中减去，从而恢复正确的补码极性。

@fig-hardware-execution-model 完整呈现了静态权重部署与动态运行期数据流在存算阵列与 SRAM 之间的分工协同机制。系统执行在时间上解耦为两个阶段：在模型部署阶段，初始化入口 `__cim_array_init` 仅执行一次，通过专用指令 `cim.array.load` 将全模型静态权重固化至阵列的指定物理坐标；在推理计算阶段，每次调用仅在 SRAM 中搬运动态输入输出，通过 `cim.bit` 指令循环驱动阵列完成位计算，并在 SRAM 内部完成移位累加与偏置加法，最后将输出写回外部宿主内存。

#figure(
  image("assets/hardware-execution-model.pdf", width: 92%, alt: "目标硬件的部署路径、运行数据流与存储分工"),
  caption: [目标硬件的部署路径、运行数据流与存储分工],
) <fig-hardware-execution-model>

== 硬件约束形式化
<sec2-2-硬件约束形式化>

受限于存算阵列的几何尺寸，单次 MVM 执行的权重矩阵必须被容纳在物理边界之内。设第 $t$ 个 MVM 对应的权重矩形为四元组 $R_t = (r_t, c_t, k_t, n_t)$，其中 $(r_t, c_t)$ 为该权重在阵列中的物理起始行与起始列坐标，$(k_t, n_t)$ 为其高度与宽度。单次硬件执行要求满足 $0 lt.eq r_t, r_t + k_t lt.eq 1024$ 以及 $0 lt.eq c_t, c_t + n_t lt.eq 512$。对于全模型中所有常驻权重矩形集合，任意两个非共享权重的物理矩形在二维空间内必须满足互不相交的几何不变式：

$ forall i eq.not j, wide [r_i, r_i + k_i) times [c_i, c_i + n_i) inter [r_j, r_j + k_j) times [c_j, c_j + n_j) = diameter . $ <eq-no-overlap>

当单个逻辑权重的尺寸超出阵列容量（即 $K > 1024$ 或 $N > 512$）时，编译器必须执行空间分块，不同切分方向直接决定了运行期中间结果的重组代数语义。沿归约轴（$K$ 轴）的行切分将大矩阵拆分，破坏了单次归约的完整性，各子窗口产生中间部分和，需要编译器显式分配中间 SRAM 暂存区并通过后续 `cim.elt add` 指令在时间轴上完成串行累加；沿输出通道轴（$N$ 轴）的列切分则保留了完整的输入归约，各子窗口计算结果天然属于互不重叠的输出通道区间，可直接原位写入不同的目的 SRAM 视图，无额外算术累加开销。

在片上存储维度，SRAM 分配必须在时间与空间双重维度上满足互斥约束。设模型生命周期中创建的第 $i$ 个物理缓冲区大小为 $s_i$ 字节，起始偏移为 $o_i$，其在操作序列上的活跃区间记为 $I_i = [l_i, r_i)$。当且仅当两个缓冲区的活跃生命周期存在交集时，其在 SRAM 上的内存地址区间才不可重叠：

$ I_i inter I_j eq.not diameter arrow.r.double [o_i, o_i + s_i) inter [o_j, o_j + s_j) = diameter . $ <eq-sram-disjoint>

同时，分配方案确定的 SRAM 峰值物理地址 $P_("SRAM") = max_i (o_i + s_i)$ 必须严格满足容量上限 $P_("SRAM") lt.eq 524,288$ 字节与硬件寻址对齐条件 $(o_i "mod" 64) = 0$。在此合法性基准之上，编译器的优化目标形式化为：在监控全模型部署权重单元总占用率 $U_("Array") = (sum_m k_m n_m) / (1024 times 512)$ 确保不超限的前提下，最小化全模型总位计算轮次 $min R_("bit") = sum_q B_q$（$B_q$ 为第 $q$ 个 MVM 窗口的有效位宽），并最小化 SRAM 峰值地址 $min P_("SRAM")$。

== 编译器总体架构
<sec2-3-编译器总体架构>

本项目通过 IREE 原生插件与 target hooks 接入编译主干：Flow 负责 executable outline 与常量捕获，
Stream 负责资源和时间线，HAL 负责设备接口、链接与序列化。Host 控制程序降低为 VM，设备物理程序
封装为 `hal.executable.binary`，共同进入 VMFB。CIM 不修改 IREE/LLVM/Torch-MLIR 上游源码。

#figure(
  image("assets/iree-cim-architecture.pdf", width: 100%, alt: "IREE 原生下降阶段与 CIM 编译器介入位置"),
  caption: [IREE 原生下降阶段与 CIM 编译器介入位置],
) <fig-iree-cim-architecture>

如 @fig-iree-cim-architecture 所示，端到端编译流水线呈现出清晰的双轨协同演进特征。宿主控制路径负责张量依赖分析与 Dispatch 任务划分，在 HAL 阶段形成资源管理与设备调用，再经过 VM 降低与字节码编码生成 VMFB；设备计算路径则通过插件入口函数 `iree_register_compiler_plugin_cim` 将专用 Pass 挂载至 IREE 的原生扩展点，形成严格的阶段职责契约：

```text
iree_register_compiler_plugin_cim
  ├─ input extension         → signed linear normalization
  ├─ preprocessing extension → optional heterogeneous + native horizontal fusion
  └─ HAL TargetBackend       → configuration / translation / linking / serialization
```

Input 阶段统一线性算子的张量形式；preprocessing 在 dispatch 划分前组织可融合计算，
随后 IREE 原生 global optimization、dispatch creation、Flow 与 Stream 继续建立计算和资源关系。
Target configuration/translation 完成两级 tiling 与逻辑 CIM 降低；HAL linking 后统一进行权重重组、
Array 放置、一次性初始化、位串行展开和 SRAM 分配，最后序列化为同源 payload/ISA。
