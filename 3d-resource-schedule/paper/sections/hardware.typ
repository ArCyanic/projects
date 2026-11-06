#import "../components.typ": *

= Hardware Abstraction

== Architecture Model

#paper-figure("figures/02-hardware.drawio.pdf", [Hardware Abstraction. (a,b) Mesh and node resources. (c) Stacked planes with shared input and readout circuits. (d) Planar sums digitized unit results; Vertical accumulates $d$ slices before conversion. Blue links carry digital results.], wide: true) <fig:hardware>

如 @fig:hardware[图](a)–(c) 所示，3D CIM 硬件系统由二维网格（2D Mesh）互联的计算节点组成，自底向上分为四级：垂直堆叠的多层存储阵列构成基础计算微元 Unit-Cube；多个 Unit-Cube 在平面上排布构成存内计算单元 Sub-Cube，支持算子内空间并行乘加；Sub-Cube 结合本地缓冲、数字合并逻辑与路由接口构成计算节点 Node；全芯片节点通过有向 2D Mesh 链路互联。在微架构上，垂直堆叠的多层阵列共享输入驱动、字线控制与读出电路。受此硬件结构约束，每个 Sub-Cube 同一时刻仅能激活单个权重算子执行乘加；共驻同一节点的多个活跃专家须在节点内串行执行，分布于不同节点的专家则可跨节点并行执行。

针对三维堆叠阵列，模型支持两类代表性的原位计算与读出方式（@fig:hardware[图](d)）：
+ *平面存内计算（Planar）*：权重沿二维平面展开，逐层激活目标阵列并由模数转换器（ADC）分别量化读出，各计算微元的数字部分和经片上数字加法树规约合并 @jang2025 @buchel2025；
+ *垂直累加（Vertical）*：输入维权重切片沿垂直深度放置，多层字线依次开启并在垂直位线电容上原位模拟累加电荷，完成深度累加后由顶层 ADC 单次量化读出，再经数字向量加法器合并组间结果 @lee2022。

为连接空间部署与时延评估，本文定义三维权重块（Weight-Cube）表征映射至节点的算子权重。每个 Weight-Cube $c$ 由三维尺寸 $(H_c, W_c, D_c)$、本地执行时间 $T_c$ 及输入输出字节数 $(V_c^"in", V_c^"out")$ 描述。其中，$(H_c, W_c, D_c)$ 刻画权重块在节点平面与堆叠深度上的存储占用，用于检验节点容量可行性；$T_c$ 涵盖节点内的输入装载、阵列计算、ADC 量化、结果合并与写出耗时；$V_c^"in"$ 与 $V_c^"out"$ 按激活张量长度与位宽折算为通信载荷，用于计算跨节点传输时间。该表示借鉴了 Timeloop、MAESTRO 与 CiMLoop 将负载与硬件资源分层抽象的思想 @timeloop2019 @maestro2019 @cimloop2024。

== Cost Model

给定权重块的输入切片数 $S$、输出区间数 $Q$ 及垂直累加深度 $d$，代价模型依计算与读出机制计算本地执行时间 $T_c$。在 Planar 配置下，输入切片在平面阵列上展开，局部结果分别量化读出后送入数字加法树。设首个切片的计算与读出时间为 $t_"mvm"$，后续切片按间隔 $t_"issue"$ 依次发射；全部切片完成后经 $ceil(log_2 S)$ 级二叉树数字加法规约，并写出 $Q$ 个输出区间，其本地执行时间为

$
T_c^"P"=t_"mvm"+(S-1)t_"issue"
+tau_"red"ceil(log_2 S)+tau_"out"Q.
$ <eq:planar>

其中 $tau_"red"$ 为单级数字加法树延迟，$tau_"out"$ 为单个输出区间的写出耗时。切片数 $S$ 决定输入切片发射跨度与数字规约级数，输出区间数 $Q$ 决定结果写出耗时。

在 Vertical 配置下，每 $d$ 个输入切片划分为一个垂直累加组，在位线模拟域累加电荷后执行单次 ADC 量化，共形成 $P=ceil(S/d)$ 组数字部分和，其本地执行时间为

$
T_c^"V"=T_"in"+t_0+d t_"step"
+(P-1)t_"add"+T_"out".
$ <eq:vertical>

其中 $T_"in"$ 与 $T_"out"$ 为输入装载与结果写出耗时，$t_0+d t_"step"$ 为 $d$ 层垂直位线模拟累加与单次 ADC 转换耗时，$(P-1)t_"add"$ 为 $P$ 组数字结果的向量加法合并耗时。增大累加深度 $d$ 可减少数字合并次数 $P-1$，但会线性增加模拟累加时间 $d t_"step"$。

实验中，Planar 与 Vertical 的时间参数分别依据 Jang 等人的 3D NAND 存内计算原型 @jang2025 与 3D-FPIM @lee2022 标定。对于跨节点通信，通信载荷为 $V$ 字节的数据包在带宽为 $B_"mesh"$ 的有向链路上单跳传输时间为 $t_"hop" (V)=ceil(V/B_"mesh")$。单个专家副本的本地执行时间 $T_e$ 由其所属投影算子权重块的 $T_c$ 累加得到；节点内串行等待与链路争用等待在第 4 章的推理执行模型中计算。
