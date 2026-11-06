本文参照 Timeloop @timeloop2019、MAESTRO @maestro2019 和 CiMLoop @cimloop2024 分层描述硬件原语及系统代价的方法，将底层 3D CIM 微架构抽象为算法可见的计算微元、自包含宏核心和片上网络拓扑。统一接口向上提供局部硬件服务时间 $T_"WC"$ 及单跳网络时延 $T_"hop"$；微观电路时序参数推导见附录 A。

== 空间拓扑层级

系统确立由微观至宏观的四级物理硬件抽象体系：

+ *阵列计算微元 Unit-Cube*：共享局部驱动与读出电路的三维阵列计算微元。单层局部矩阵向量乘（MVM）覆盖的物理尺寸为 $h_u times w_u$，物理存储深度为 $D_s$。
+ *自包含三维存算宏核心 Sub-Cube*：由 $N_H times N_W$ 个 Unit-Cube 在平面平铺构成的存算宏单元，物理平面尺寸为 $(H, W) = (N_H h_u, N_W w_u)$。Sub-Cube 内部自包含输入分发总线、存算阵列、部分和累加网络与输出暂存缓冲，对外表现为*单一互斥计算端口*。
+ *计算节点 Node*：片上网络的基本站点 $n in {0, 1, dots, G_H G_W - 1}$，由 Sub-Cube 存算核心及其外围网络与控制逻辑电路构成。该抽象界定了两类物理数据流转域：
  - *核心内部存算与部分和求和（Intra-Core Partial-Sum Aggregation）*：完全在 Sub-Cube 内部完成，计入本地硬件服务时间 $T_"WC"$；
  - *跨节点网络数据通信（Inter-Node Network Communication）*：由外围路由器和物理链路承载，负责节点间的数据路由转发及集合通信，计入网络传输与排队时延。
+ *整机系统 3D Cube*：由 $G_H times G_W$ 个计算节点通过二维网格（2D Mesh）互联构成的分布式片上存算集群。

== 统一硬件抽象

统一硬件抽象以最终读出前是否沿深度累加部分和为分界，将代表性 3D CIM 架构归入 Planar 与 Vertical 两类计算范式。ICCD 2025、Nature 3D AIMC、Sharma 等人的异构介质架构和 NASiC 均落入 Planar：它们共享平面局部 MVM 与数字域规约语义，同时分别扩展存储介质组织、执行资源作用域和阵列选通能力。3D-FPIM 落入 Vertical，以深度模拟累加和单次量化读出实例化另一条计算路径。

*Planar 平面存算范式* 将一个计算区域的矩阵权重平铺于二维物理平面。该区域的局部深度为 1，控制器单次选通一个存储层，二维阵列完成模拟乘加并由模数转换器（ADC）独立读出局部数字结果。输入维切片产生的部分和由 Sub-Cube 内部数字规约资源合并，多列输出在暂存区拼接提交。超出单个平面的算子由 5.1 节的空间编译器切分并沿 Weight-Cube 深度折叠。ICCD 2025 与 Nature 3D AIMC 分别给出 3D NAND 平面计算及 3D AIMC 逐层计算的具体组织 @jang2025 @buchel2025。

*Vertical 垂直累加范式* 将输入向量的切片沿垂直深度堆叠，使深度维度直接参与单次矩阵乘加计算。在计算执行时，多层物理字线依次选通放电，各切片的模拟乘加电流在垂直位线上原位完成电荷累加，在最顶层完成全部累加后由模数转换器（ADC）一次性读出，同列区间的微元组输出在数字域由内置向量加法器聚合。该范式的核心特征是*“深度空间折叠、垂直原位模拟累加、单次 ADC 读出”*，显著压缩了平面物理面积并降低了 ADC 转换开销。文献中的垂直堆叠闪存芯片 @lee2022 作为该范式的物理实现实例，为垂直模拟电荷累加提供了电路时序标定。

Sharma 的多介质分层由 Unit-Cube 介质属性、Sub-Cube 深度分区和内部垂直互连表达；NASiC 的阵列级专家选通由 Planar Unit-Cube 的执行谓词表达 @sharma2025 @nasic2026。它们与 ICCD、Nature 3D AIMC 和 3D-FPIM 共享同一套空间、执行及网络抽象。Sharma 与 NASiC 尚未报告足以闭合比赛规模节点容量、完整 Weight-Cube 服务事件图和端到端执行锚点的参数，本报告因此没有为二者建立独立数值配置或性能实验。

@tab:report-hardware-role-summary 比较五种原型的几何层级。$U=(h_u,w_u,D_s)$ 表示论文原生 Unit-Cube，$S=(H,W,D_s)$ 表示论文给出的系统宏组织。进入统一抽象后，硬件参数配置将这些原型尺寸归一化为算法使用的逻辑几何。

#figure(
  table(
    columns: (1.05fr, 0.85fr, 1.75fr, 1.75fr),
    align: (left, left, center, center),
    table.header([硬件原型], [计算范式], [原生 Unit-Cube $U$], [原文系统宏 $S$]),
    [ICCD 2025 @jang2025], [Planar], [$128 times 512 times 128$], [$16384 times 65536 times 128$],
    [Nature CS 2025 @buchel2025], [Planar], [$512 times 512 times 256$], [$8192 times 8192 times 256$],
    [3D-FPIM @lee2022], [Vertical], [$128 times 128 times 64$], [$512 times 768 times 64$],
    [Sharma 等 @sharma2025], [Planar 扩展], [$128 times 128 times 16$], [$12800 times 13312 times 16$],
    [NASiC @nasic2026], [Planar 扩展], [$128 times 128 times 162$], [$4096 times 131072 times 162$],
  ),
  caption: figure.caption(position: top, [代表性硬件原型的 Unit-Cube 与系统宏几何。五种架构均由 Unit-Cube、Sub-Cube、Node 与 Mesh 四级模型表达。]),
) <tab:report-hardware-role-summary>

== 硬件服务时间模型

对于单个未折叠的 Weight-Cube，单次调用独占 Sub-Cube 计算端口，其硬件服务事件图由输入分发、存算执行、部分和规约及结果写出四类微观事件组成：

$
G_"WC" = G_"in" union G_"compute" union G_"reduce" union G_"out",
quad
T_"WC" = op("Makespan")(G_"WC"; X).
$

其中 $X$ 表示输入通路、计算微元、数字规约树与输出缓冲的共享硬件资源约束。在依赖关系与物理资源允许时，各阶段事件流水重叠推进，正式服务时间严格取事件图 makespan。两类范式在各自依赖约束与硬件组织下的闭式服务时间模型推导如下：

*Planar 闭式服务时延*：计算区域在二维平面展开。设 $S = ceil(K_c / h_u)$ 为输入切片数，$Q = ceil(M_c / w_u)$ 为输出区间数。输入切片以发射间隔 $T_"issue"$ 流水进入局部 MVM，首轮切片完成前的流水跨度为：

$
T_"span"(S) = T_"compute" + T_"issue" dot (S - 1).
$

同一输出区间的 $S$ 份局部结果通过树形数字加法器规约，随后写出 $Q$ 个输出区间。规约与写出构成联合尾部时延：

$
T_"tail"(S, Q) = T_"reduce"(S) + T_"out"(Q) = tau_"red" ceil(log_2 S) + tau_"out" Q.
$

Planar 计算区域的端到端事件图关键路径时延为：

$
T_"WC"^"Planar"(S, Q) = T_"span"(S) + T_"tail"(S, Q).
$

*Vertical 闭式服务时延*：$S = ceil(K_c / h_u)$ 个输入切片沿垂直深度以累加深度 $D_"acc"$ 分组，平面输入组数为 $P = ceil(S / D_"acc")$。单个 Unit-Cube 沿垂直位线完成原位模拟积分累加并执行单次量化读出，其局部关键路径时延为：

$
T_"unit"^"V"(D_"acc") = t_"fixed" + t_"step" D_"acc".
$

同一输出区间的 $P$ 个 Unit-Cube 读出结果由片上向量加法器规约，Vertical 计算区域的端到端事件图关键路径时延为：

$
T_"WC"^"Vertical" = T_"in"(K_c) + T_"unit"^"V"(D_"acc") + (P - 1) t_"vec-add" + T_"out"(M_c).
$

累加深度 $D_"acc"$ 联合决定了模拟积分时间、平面资源占用与数字规约链长度。硬件编译器枚举合法整数深度，自动选取使 $T_"WC"^"Vertical"$ 最小的最优配置。

本节定义单个未折叠 Weight-Cube 的基础计算时间。超出 Sub-Cube 物理平面的矩阵规整、深度折叠与算子聚合由第 5.1 节空间编译器统筹处理；微观电路时序参数、事件流水重叠与硬件原型端到端锚点详见附录 A。

== 片上网络通信代价模型

全系统 $G_H times G_W$ 个计算节点由 2D Mesh 网格互联，相邻节点间通过独立的反向有向链路通信。设有效链路带宽为 $B_"mesh"$，单位为 Byte/ns；大小为 $V$ Byte 的激活载荷单跳传输时延为 $T_"hop"(V) = ceil(V / B_"mesh") " ns"$。网络中每条有向链路维护独立的可用时间日历，传输任务按就绪与空闲时序推进，精确计入链路排队延迟。

MoE 层的跨节点通信在 2D Mesh 上物化为多播分发与树形规约两阶段集合数据流（如 @fig:report-moe-multicast-reduction 所示）：
- *多播分发*：输入激活沿最短路径多播树边集 $E_"dispatch"$ 分发至各执行节点（公共链路单份传输并在分支处复制），总链路工作量为 $W_"dispatch" = |E_"dispatch"| T_"hop"(V_"in")$；
- *树形规约*：各节点计算结果沿最短路径规约树边集 $E_"reduce"$ 向汇聚根节点汇聚，总链路工作量为 $W_"reduce" = |E_"reduce"| T_"hop"(V_"out")$。

规约根产出的完整层激活直接作为下一层多播分发的输入源点，闭合跨层状态流转。

#figure(
  image("/assets/figures/moe-multicast-reduction.png", width: 100%),
  caption: [2D Mesh 上的 MoE 多播分发树与树形规约通信过程。（a）输入激活沿最短路径多播树从源节点 $S$（$N_5$）分发至各目标执行节点，公共链路单份传输并在分支处复制；（b）各目标节点完成计算后，沿规约树向规约根 $R$（$N_9$）汇聚，根节点输出直接作为下一层多播起点。],
) <fig:report-moe-multicast-reduction>
