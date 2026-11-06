#set document(title: "Supplementary Material: A Deployment and Execution Framework for MoE Inference on 3D CIM Systems", author: ())
#set page(paper: "a4", margin: (x: 22mm, top: 19mm, bottom: 19mm), numbering: "S–1", number-align: center)
#set text(font: ("Libertinus Serif", "Noto Serif CJK SC"), lang: "zh", region: "CN", size: 10.5pt, fill: rgb("#202B33"))
#set par(justify: true, leading: 0.6em, spacing: 0.6em, first-line-indent: 1em)
#set heading(numbering: "A.1")
#show heading.where(level: 1): it => block(above: 15pt, below: 7pt)[#text(font: "Noto Sans CJK SC", size: 13pt, weight: "bold", it)]
#show heading.where(level: 2): it => block(above: 8pt, below: 4pt)[#text(font: "Noto Sans CJK SC", size: 11pt, weight: "medium", it)]
#set math.equation(numbering: "(S1)")
#show math.equation: set text(font: "New Computer Modern Math", size: 10pt)
#show math.equation.where(block: true): set block(above: 5pt, below: 5pt)
#set figure(gap: 5pt)
#show figure: set text(lang: "en", region: "US")
#show figure.caption: it => {
  set text(size: 9pt)
  set par(first-line-indent: 0pt, leading: 0.45em)
  it
}
#set cite(style: "ieee")
#let s-table(caption, columns, ..cells) = figure(
  {
    set text(size: 9pt, lang: "en", region: "US")
    set par(first-line-indent: 0pt, leading: 0.4em)
    table(columns: columns, inset: (x: 5pt, y: 3pt), align: left,
      stroke: (x: none, y: 0.35pt + rgb("#D7DEE4")), ..cells)
  },
  kind: table, supplement: [Table], numbering: "S1",
  caption: figure.caption(position: top, caption),
)

#align(center)[
  #text(font: "Noto Sans CJK SC", size: 18pt, weight: "bold")[Supplementary Material]
  #v(5pt)
  #text(size: 10pt)[Hardware Models, Algorithm Details, and Extended Results]
]
#v(10pt)

本材料补充硬件执行开销推导、空间编译约束、算法搜索规则与扩展实验结果，各部分可按 @tab:supp-overview[表] 对应主题独立阅读。

#s-table([Supplementary Material Overview.], (1.05fr, 0.8fr, 2fr),
  table.header([*Section*], [*Main paper*], [*Content in the main paper*]),
  [A. Hardware costs], [§3], [Weight-Cube representation, cost expressions, parameters, and sources.],
  [B. Spatial compilation], [§3, §4.2.1], [3D feasibility constraints and node capacity.],
  [C. Decision rules], [§4.3], [Mapping workflow, scheduling objectives, and selection rules.],
  [D. Performance projections], [§4.2.2, §4.2.3], [Critical-path timing, resource bounds, and optimization insights.],
  [E. Additional results], [§5], [Overall performance, hardware-aware mapping, and scheduling ablation.],
) <tab:supp-overview>

= Hardware Cost Derivation <app:cost>

统一硬件抽象向映射器提供块几何、服务时间与通信载荷。下面给出两类配置的时序模型及参数，所有时间以 ns 计，带宽以 Byte/ns 计；数值上 $1 " GB/s"=1 " Byte/ns"$。服务时间按输入分发、局部计算、规约与写出的依赖关系计算。

== Planar Timing Model

Planar 配置沿用 3D NAND 平面计算的组织方式 @jang2025，局部输入切片长度为 128，局部输出区间长度为 512。设单个计算切片的逻辑输入、输出长度为 $K$、$M$，则 $S=ceil(K/128)$，$Q=ceil(M/512)$。W8A8 配置下，每个 128 元素输入切片占 128 Byte，经 2 GB/s 输入通路传输后，每 64 ns 发射一片。

局部 MVM 服务基准取 2000 ns。后续输入切片与已发射切片的计算重叠，从首次发射到最后一片完成的时间为

$
T_"span" (S)=2000+64(S-1).
$ <eq:span>

当前模型采用 $7168 times 7168$ 算子的 8270 ns 服务锚点。该形状对应 $S^*=56$、$Q^*=14$，输入计算跨度为 $2000+64 times 55=5520$ ns，余下的规约与输出时间为

$
T_"tail"^*=8270-5520=2750.
$ <eq:tail-anchor>

将规约部分按二叉树深度 $ceil(log_2 S)$ 缩放，将写出部分按输出区间数 $Q$ 缩放。令 $alpha$ 表示锚点尾部中分配给规约的比例，则

$
T_"red" (S)=op("round")(2750 alpha frac(ceil(log_2 S),6)),
$ <eq:red>
$
T_"out" (Q)=op("round")(2750(1-alpha)frac(Q,14)).
$ <eq:out>

实验配置取 $alpha=0.5$，将余下时间均分给规约与输出项，分别得到约 229.17 ns 的每级规约系数和约 98.21 ns 的每输出区间系数。实现先分别取整规约项与写出项，再与输入计算跨度相加：

$
T_"section"^"P"=T_"span" (S)+T_"red" (S)+T_"out" (Q).
$ <eq:planar-supp>

== Vertical Timing Model

Vertical 配置采用 3D-FPIM 的垂直累加执行组织 @lee2022。首层建立与驱动耗时为 $105+32$ ns，后续每层选择与驱动为 $170+32$ ns，末端量化读出为 256 ns。累加深度为 $d$ 时，局部模拟计算时间为

$
T_"unit"^"V" (d)=(105+32)+(d-1)(170+32)+256=202d+191.
$ <eq:vertical-unit>

输入被分成 $S=ceil(K/128)$ 片，每 $d$ 片组成一个微元组，组数为 $P=ceil(S/d)$。同一输出区间的 $P$ 份结果采用向量加法合并，每次加法耗时 128 ns，因此数字规约时间为 $128(P-1)$。

输入输出服务按激活位宽计算。对 $n$ 个、每个 $a$ bit 的逻辑元素，消息字节数为

$
V(n,a)=ceil(frac(n a,8)).
$ <eq:bytes>

设输入、输出带宽为 $B_"in"$、$B_"out"$，则完整服务时间为

$
T_"section"^"V" (K,M,d)
=ceil(frac(V(K,a),B_"in"))+(202d+191)
+128(ceil(S/d)-1)+ceil(frac(V(M,a),B_"out")).
$ <eq:vertical-supp>

当前 Vertical 配置取 $a=5$、$B_"in"=B_"out"=1$。编译器在 $1<=d<=min(S,64)$ 的整数范围内比较服务时间；时间相同时，依次选择填充后的输入片数 $ceil(S/d)d$ 更小、深度 $d$ 更小的方案。

== Operator Examples

Gate/Up 复合投影具有两倍中间维度的物理权重列，逻辑输出在门控合并后收缩为中间维度。空间占用按物理权重列计，输出服务按逻辑输出元素计。DeepSeek-V3 路由专家的 Gate/Up 逻辑接口为 $7168 -> 2048$，物理权重列数为 4096；Down 接口为 $2048 -> 7168$。

#s-table([Operator Service Times (ns). Planar input/pipeline times include local computation.], (0.9fr, 0.9fr, 1fr, 1fr, 1.15fr, 0.75fr),
  table.header([*Profile*], [*Operator*], [*Input / pipeline*], [*Local compute*], [*Reduce + output*], [*Total*]),
  [Planar], [Gate/Up], [5520], [Included], [$1375+393$], [7288],
  [Planar], [Down], [2960], [Included], [$917+1375$], [5252],
  [Vertical], [Gate/Up], [4480], [1605], [$896+1280$], [8261],
  [Vertical], [Down], [1280], [999], [$384+4480$], [7143],
) <tab:service-example>

Vertical Gate/Up 取 $d=7$、$P=8$，Down 取 $d=4$、$P=4$。其服务时间分别为 $4480+1605+896+1280=8261$ ns 和 $1280+999+384+4480=7143$ ns。Planar 对规约与输出项独立取整后得到 7288 ns 和 5252 ns。专家服务时间取两项之和，输入输出消息则由专家边界上的逻辑激活长度确定。

= Spatial Compilation <app:packing>

几何编译将逻辑算子矩阵映射为节点内的三维长方体权重块。离线映射的容量校验与最终部署的坐标装箱共用同一组几何约束：权重块尺寸按微元步长对齐，放置受节点物理边界限制。

== Matrix Partitioning

设矩阵具有 $K$ 个输入、$M$ 个逻辑输出和 $C_w$ 个物理权重列。Planar 的展开高度为 $H_0=K$，局部深度为 $d=1$；Vertical 先确定累加深度，再令 $H_0=128 ceil(ceil(K/128)/d)$。在节点平面 $H times W$ 内，输入和输出方向的折叠数为

$
A=ceil(H_0/H), quad B=ceil(C_w/W), quad N_"section"=A B.
$ <eq:fold-count>

定义对齐算子 $op("align")_u (x)=u ceil(x/u)$，则各切片与完整权重块的尺寸为

$
H_"section"=op("align")_(h_u) (ceil(H_0/A)),
quad W_"section"=op("align")_(w_u) (ceil(C_w/B)),
$ <eq:fold-shape>
$
(H_c,W_c,D_c)=(H_"section",W_"section",A B d).
$ <eq:cube>

当前编译器采用等形切片，边缘区域按微元步长填充。各切片在同一节点内串行执行；高度折叠产生输入维部分和，宽度折叠产生不同输出区间，最终在节点内完成合并。单块服务时间为 $N_"section" T_"section"$，输入输出接口保持原算子的逻辑长度。

== Geometric Packing

每个权重块以固定方向放置，块 $c$ 的起点为 $(x_c,y_c,z_c)$，需要满足边界约束和两两包围盒分离。对任意两个块 $c$、$d$，至少在一个坐标轴上无重叠，例如在高度方向满足 $x_c+H_c<=x_d$ 或 $x_d+H_d<=x_c$。所有节点分别独立求解放置。

装箱顺序按节点编号升序、高度降序、宽度降序、深度降序和稳定对象编号升序确定。节点内各块深度相同时，使用 First-Fit Shelf：在已有层架中选择高度和剩余宽度都满足要求的第一个位置，随后按需要开辟层架与深度切片。混合深度采用 XY Skyline：维护底面高度图，对块的每个候选底面位置计算

$
z(x,y)=max_((u,v) in "footprint"(x,y)) op("Top")[u,v],
$ <eq:skyline>

选择最小的 $(z,y,x)$，检查 $z+D_c<=D_s$，并将覆盖区域的高度更新为 $z+D_c$。高度图维护各坐标已占用的最高表面，新权重块在该表面之上继续放置。

节点容量由固定权重和标准专家模板共同确定。系统通过二分搜索确定各节点可容纳的标准专家槽位数 $C_n$，每次探测均调用装箱内核。最终部署再次执行完整装箱：几何尺寸与起始坐标用于物理有效性复核，专家驻留关系与服务时间则供运行时调度使用。

= Algorithm Details <app:decisions>

以下给出映射算法的增量评价与候选选择规则。

== Incremental Gain Evaluation

设层 $l$ 的结构代价为 $C_l (q,s;X)$，规约根转移为 $f_l (q,s;X)$。固定后续层的部署和运行时规则后，后缀价值记录从每个候选源节点出发的剩余代价：

$
V_l (q,s;X)=C_l (q,s;X)+V_(l+1) (q,f_l (q,s;X);X),
quad V_(L+1)=0.
$ <eq:suffix-supp>

对当前层的候选移动 $m$，该移动仅影响激活了被移动专家的路由集合 $cal(Q)_m$。设旧、新层代价为 $C_l,C_l'$，旧、新规约根为 $u_l,u_l'$，则在冻结后缀下，移动增益为

$
g(m)=sum_(q in cal(Q)_m)
[C_l (q,s_l;X)-C_l'(q,s_l;X')
+V_(l+1) (q,u_l;X)-V_(l+1) (q,u_l';X)].
$ <eq:gain>

后缀表在一次前向扫描开始时从末层反向构造。扫描到当前层时，后续层保持扫描起点的布局；已经提交的前序层决定当前输入状态。层内移动据此使用同一后缀表，提交一层的最大正增益前缀后，重新计算前向状态，再处理下一层。一次完整扫描结束后重新评价全模型结构目标，并为下一轮构造新后缀表。

层内 FM 扫描每步选择收益最大的合法“专家—目标节点”移动，并锁定该专家。容量计数随着迁移立即更新，释放出的槽位可供后续动作使用。扫描在访问完当前层专家，或距最佳前缀累计达到 $8N$ 步时结束，其中 $N$ 为节点数。最终只提交累计收益最大的正前缀。该邻域通过逐步使用空闲槽位组织迁移，固定预算阶段另通过同层副本交换保持逐层节点占用。

== Candidate Selection

每轮追加副本后的中间部署记为 $tilde(X)$，自身满足回退参照 $r_"local"(tilde(X))=0$。随后的位置搜索保持各专家的副本数和逐层节点占用不变，生成四个 Decode 累计搜索前缀与最多八个 Prefill 交换方案，并与中间部署 $tilde(X)$ 一起构成至多十三个候选。各候选方案经三维装箱后，在同一训练路由上执行物理评价。

令 $J_P^t (X)$ 为窗口规模 $t$ 下的完成时间。候选方案以

$
r_"local" (X)=max_(t in {32,128,512})
(frac(J_P^t (X),J_P^t (tilde(X)))-1)
$ <eq:local-regret>

衡量 Prefill 回退，系统保留 $r_"local"<=0.02$ 的方案，并在达标候选中选取 Decode 平均时延最低者。

两条搜索路径的部署选择在验证集上进行。每个规模的理想参照为两条轨迹该规模的最好值 $m_t$，候选的回退为 $r(X)=max_t (frac(J_P^t (X),m_t)-1)$。有效门限取 $epsilon_k=max(0.02,min_X r(X))$，再从门限内选择 Decode 平均时延最低者。对不同窗口交叉领先的候选，$min_X r(X)$ 给出当前候选集合的最小最大回退。下一档预算继续分别继承各轨迹自己的入选布局。

== Scheduling Rules

#s-table([Runtime Scheduling Rules.], (1.1fr, 2.8fr),
  table.header([*Decision*], [*Priority order or execution rule*]),
  [Decode replica and root], [Critical-branch latency; communication-tree edges; node ID.],
  [Prefill replica], [Assigned work + expert execution time; input arrival; node ID; replica ID.],
  [Prefill reduction root], [Tree edges; maximum depth; total Manhattan distance; node ID.],
  [Compute arbitration], [Token order; execution stage; ready time; stable task ID.],
  [Directed link], [Each hop starts when its data and link are both available.],
)

Prefill 每选定一个专家副本，立即更新临时累计分配工作量，后续专家读取更新后的累计量。多播公共边传输一份完整消息，规约节点在本地结果与子节点结果齐备后发送局部和。候选绑定策略之间保持相同的规约根规则和最短路径树，由此单独评价轮转和累计工作量分派对执行的影响。

= Performance Decomposition <app:projection>

性能分析中，Decode 分析关键路径耗时，Prefill 统计共享资源占用。以下给出正文投影关系的条件和推导。

== Critical-Path Metrics

在单层等服务时间专家的条件下，关键节点分支执行 $k_l$ 个活动专家。将其中最后一个专家作为基础服务，其前序工作对应 $N_("serial",l)=k_l-1$ 次串行服务。输入与输出消息的单跳服务时间分别为 $t_("in",l)$、$t_("out",l)$，关键执行分支上的跳数分别为 $N_("in",l)$、$N_("out",l)$，于是

$
T_("node",l)=N_("serial",l)T_(e,l),
quad T_("mesh",l)=N_("in",l)t_("in",l)+N_("out",l)t_("out",l).
$ <eq:projection-counts>

专家服务时间不同时，同节点前序工作改为逐专家服务时间之和；跨方向载荷不同时，通信按各消息服务逐边累加。执行器还单独记录规约等待和链路争用。稠密层、专家基础服务、串行、通信及等待共同组成整条执行链的时延。

布局 $X$ 在评价带宽 $B$ 下的关键分支为 $i^* (X,B)=arg max_i C_i (X,B)$。改变 $B$ 会改变传输延迟并可能切换最慢执行分支。在相同带宽下重放两个布局，可以比较布局在跳数与节点串行数上的结构差异。

#block(breakable: false)[
== Resource Bounds

对一个从时刻 0 开始的 Prefill 窗口，记完成时间为 $J_P$。节点 $n$ 的占用指示函数为 $b_n (t) in {0,1}$，其累计计算工作量为

$
W_("comp",n)=integral_0^(J_P) b_n (t) dif t.
$ <eq:work-integral>
]

由 $b_n (t)<=1$ 得 $W_("comp",n)<=J_P$。有向链路也具有单位服务能力，同理 $W_("comm",j)<=J_P$。因此固定绑定和传输方案对应的资源界为

$
R_"res"=max(max_n W_("comp",n),max_j W_("comm",j))<=J_P.
$ <eq:resource-supp>

执行程序另外提供强制依赖链的服务下界 $L_"dep"$。当前评价器在每个窗口采用

$
B_"exec"=max(R_"res",L_"dep"),
quad Delta_"exec"=J_P-B_"exec".
$ <eq:full-bound>

这里的资源工作量由已选定的副本和通信树产生，$L_"dep"$ 由程序依赖及服务时间产生。差值 $Delta_"exec"$ 表示完成时间超出理论下界的部分，源于依赖等待、资源争用以及流水线填充与排空。当 $R_"res">=L_"dep"$ 时，该表达式即为正文使用的资源峰值残差。

== Performance Projections

令 $macron(W)_"comp"$、$macron(W)_"comm"$ 分别为节点与有向链路的平均工作量，峰值工作量记为 $W_"comp"^max$ 和 $W_"comm"^max$。对单窗口定义

$
E_"comp"=frac(macron(W)_"comp",J_P),
quad H_"comp"=frac(W_"comp"^max-macron(W)_"comp",J_P),
$ <eq:compute-proj>
$
E_"comm"=frac(macron(W)_"comm",J_P),
quad H_"comm"=frac(W_"comm"^max-macron(W)_"comm",J_P),
$ <eq:comm-proj>
$
H_"exec"=frac(Delta_"exec",J_P).
$ <eq:exec-proj>

$E_"comp"$ 与 $E_"comm"$ 分别给出平均计算与通信利用率，$H_"comp"$ 与 $H_"comm"$ 给出负载峰均差，$H_"exec"$ 给出下界之外的额外调度延迟比例。计算和通信可以重叠，二者通过最大值共同决定窗口下界，满足

$
max(E_"comp"+H_"comp", E_"comm"+H_"comm",frac(L_"dep",J_P))+H_"exec"=1.
$ <eq:five-identity>

令全系统瞬时计算利用率为 $u(t)=frac(1,N)sum_n b_n (t)$，将节点工作量积分式对节点求和并交换积分次序，得到

$
E_"comp"=frac(1,J_P)integral_0^(J_P)u(t)dif t,
quad 1-E_"comp"=frac(1,J_P)integral_0^(J_P)(1-u(t))dif t.
$ <eq:utilization-supp>

因此各节点计算工作量与时间线上的计算占用对应。热点复制主要降低峰均差，累计工作量分派主要平衡副本负载。当批处理窗口增大后，节点在主要执行区间接近连续满载，空闲时间主要出现在开始和结束阶段。

跨多个窗口汇总时，不同窗口的瓶颈资源可能不同，因此系统先逐窗口计算工作量、峰值与 $B_"exec"$，再跨窗口求均值并除以平均完成时间（例如汇总残差为 $macron(J)_P-macron(B)_"exec"$）。

= Additional Experiments <app:results>

本节给出跨模型与扩展复制预算的评测结果。

== Cross-Model Evaluation

三模型实验采用 2 GB/s 链路带宽和约 20% 额外专家副本。Qwen2 与 DeepSeek-V2-Lite 使用公开路由数据集，DeepSeek-V3 使用合成路由数据。节点平面固定为 $8192 times 16384$，采用 1.5 倍模型权重容量规则，节点深度随模型体积变化。输入规格将共享 FFN 按标准专家粒度展开。

#let cross = json("/artifacts/results/cross-model-20pct.json")
#let number(x, digits: 2) = str(calc.round(x, digits: digits))
#let performance-ratio(base, selected) = base / selected

#s-table([Cross-Model Configurations. Expert counts are per MoE layer (shared FFNs are partitioned into standard-expert-sized blocks); replicas are additional full experts.], (1.8fr, 0.9fr, 1.1fr, 0.65fr, 0.65fr, 0.75fr, 0.8fr),
  table.header([*Model*], [*Dense / MoE*], [*Routed / shared*], [*Top-k*], [*Depth*], [*Replicas*], [*Budget (%)*]),
  ..cross.models.map(m => {
    let s=m.specification
    let p=m.profiles.planar
    ([#m.name], [#s.dense_layers/#(s.model_layers - s.dense_layers)], [#s.routed_experts/#s.shared_experts], [#s.top_k], [#p.node_geometry.at(2)], [#p.extra_replicas], [#number(p.realized_extra_replica_percent, digits: 3)])
  }).flatten(),
) <tab:cross-spec>

训练、验证和测试区间各包含 4096 条路由；超图拟合使用训练区间前 1024 条。验证阶段以完整 Decode 路由及每种 Prefill 规模的一个窗口选择部署。测试阶段冻结零复制计算均衡基准和约 20% 入选部署，在 4096 条 Decode 路由和每种规模的八个 Prefill 窗口上评价。归一化速度与吞吐量均以该模型、该计算配置的测试基准为 1。

#s-table([Cross-Model Performance. Normalized Decode speed and Prefill throughput at ≈20% replication; each baseline is 1. B/H denote compute-balanced/hypergraph initial placements.], (1.75fr, 0.8fr, 0.55fr, 0.75fr, 0.7fr, 0.7fr, 0.7fr),
  table.header([*Model*], [*Profile*], [*Init.*], [*Decode*], [*T32*], [*T128*], [*T512*]),
  ..cross.models.map(m => {
    ("planar", "vertical").map(p => {
      let e=m.profiles.at(p)
      let b=e.baseline
      let s=e.selected
      ([#m.name], [#(if p=="planar" {"Planar"} else {"Vertical"})], [#(if e.selected_anchor=="compute-balanced" {"B"} else {"H"})],
       [#number(performance-ratio(b.decode.mean_ns,s.decode.mean_ns))],
       ..("32","128","512").map(t => [#number(performance-ratio(b.prefill.at(t).mean_ns,s.prefill.at(t).mean_ns))]))
    }).flatten()
  }).flatten(),
) <tab:cross-result>

六组配置的 Decode 时延改善为 15.18%–18.46%，Prefill 三种批次规模改善为 3.86%–12.61%。DeepSeek-V2-Lite 的 T512 改善为 9.56%／9.17%，Qwen2-57B-A14B 为 3.88%／3.86%，分别对应 Planar／Vertical。专家规模、路由统计和硬件执行时间共同影响复制收益及起点选择。

== Extended Replication Budgets

此处将 DeepSeek-V3 的两条搜索路径推进至 20% 预算，覆盖 Planar 与 Vertical 及 0.5、2、8 GB/s 三档带宽。节点逻辑空间为 $8192 times 16384 times 460$，评价使用验证集及计算均衡单副本基准。

#let formal = json("/paper/data/results-20pct.json")
#s-table([Performance at ≈20% Replication. Normalized Decode speed and Prefill throughput relative to the single-copy compute-balanced baseline (1); bandwidth in GB/s.], (1fr, 0.9fr, 0.85fr, 0.85fr, 0.85fr, 0.85fr),
  table.header([*Profile*], [*Bandwidth*], [*Decode*], [*T32*], [*T128*], [*T512*]),
  ..("planar", "vertical").map(p => {
    ("0.5", "2.0", "8.0").map(bw => {
      let e = formal.main.at(p).at(bw)
      let b = e.baseline
      let s = e.selected.last()
      ([#(if p=="planar" {"Planar"} else {"Vertical"})], [#number(float(bw))],
       [#number(performance-ratio(b.decode.mean_ns,s.decode.mean_ns))],
       ..("32","128","512").map(t => [#number(performance-ratio(b.prefill.at(t).mean_ns,s.prefill.at(t).mean_ns))]))
    }).flatten()
  }).flatten(),
) <tab:budget20>

10%–20% 区间使 Decode 改善量再增加 3.00–5.85 个百分点，T512 改善量变化为 +0.06 至 +0.39 个百分点。新增副本继续扩大关键路径可选择的节点组合，大并发批次的峰值计算工作量已经接近平均工作量。两类目标的边际收益因而在较高预算处分化。

== Routing Source Validation

在 Qwen2 与 DeepSeek-V2-Lite 上对比公开路由与合成路由的测试收益。经实验对比，两类路由下的优化趋势一致，验证了合成路由在评估大模型扩展性时的有效性。

#s-table([Routing Source Comparison. Normalized Decode speed and Prefill throughput (baseline = 1) under public and synthetic routes at #box[2 GB/s] and ≈20% replication.], (1.4fr, 0.85fr, 0.85fr, 0.85fr, 0.85fr, 0.85fr),
  table.header([*Model*], [*Profile*], [*Source*], [*Decode*], [*T32*], [*T512*]),
  ..cross.source_comparison.pairs().map(((model, profiles)) => {
    ("planar", "vertical").map(profile => {
      ("public", "synthetic").map(source => {
        let gains = profiles.at(profile).at(source).gains
        ([#(if model == "deepseek-v2-lite" { "DeepSeek-V2-Lite" } else { "Qwen2-57B-A14B" })],
         [#(if profile == "planar" { "Planar" } else { "Vertical" })],
         [#(if source == "public" { "Public" } else { "Synthetic" })],
         [#number(1 / (1 - gains.decode / 100), digits: 3)],
         ..("32", "512").map(t => [#number(1 / (1 - gains.prefill.at(t) / 100), digits: 3)]))
      }).flatten()
    }).flatten()
  }).flatten(),
) <tab:routing-source-comparison>
#v(8pt)
#heading(numbering: none)[References]
#block[
  #set text(size: 9pt, lang: "en", region: "US")
  #set par(first-line-indent: 0pt, leading: 0.45em)
  #bibliography("references.bib", style: "ieee", title: none)
]
