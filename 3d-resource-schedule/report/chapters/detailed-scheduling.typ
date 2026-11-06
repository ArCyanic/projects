== Dataflow Scheduling

权重部署完成后，各专家的副本常驻于指定节点，部署结果记录其位置与计算服务时间。推理时，片上网络将 Token 的激活向量送至这些节点，节点使用常驻权重执行计算。数据流调度依据当前 Token 的路由结果选择执行副本，组织输入分发和输出汇合，并安排共享节点与链路上的任务执行。

=== Layer Execution

一层 MoE 的执行从输入节点上的激活向量开始。路由结果确定本层激活的专家后，调度器从各专家的可用副本中选择执行位置，将同一输入沿多播树送至目标节点。节点收到输入后执行本地专家，同节点的多个专家串行计算，不同节点可以并行。专家输出先在本地合并，再沿规约树逐级汇合，最终形成规约根上的本层输出。下一层从这个节点分发输入，因而本层的汇合位置也影响后续传输距离。

副本和规约根确定后，执行器依据数据依赖推进计算与传输。计算任务在输入齐备且所在节点空闲时启动。输入分发在树的分支节点向不同方向复制，规约节点在本地结果与子节点结果齐备后向父节点发送局部和。每条有向链路按可用时间服务传输，数据逐跳到达下一节点。调度器因此既要选择数据经过的节点，也要安排多个就绪任务对计算与通信资源的使用。

Decode 与 Prefill 都遵循上述层内数据流。Decode 调度围绕单 Token 的逐层执行，优先缩短最慢分支。Prefill 中多个 Token 共享同一部署和片上资源，调度器需要分散持续到达的专家任务，并让各 Token 按数据依赖并发推进，以缩短整个窗口的完成时间。

@tab:report-scheduling-axes 将上述执行过程中的选择归纳为五个调度维度。副本绑定和规约根选择确定计算与汇合位置，计算仲裁和链路仲裁安排就绪任务的执行次序，传输策略规定数据沿哪些路径、以何种粒度转发。两阶段分别选择执行位置，并共用最短路径树与逐跳传输规则。

#figure(
  table(
    columns: (0.82fr, 0.95fr, 1.32fr, 1.48fr, 1.62fr),
    align: (left, left, left, left, left),
    table.header(
      table.cell(fill: rgb("#DCEAF7"))[*层级*],
      table.cell(fill: rgb("#DCEAF7"))[*决策轴*],
      table.cell(fill: rgb("#DCEAF7"))[*控制对象*],
      table.cell(fill: rgb("#DCEAF7"))[*Decode*],
      table.cell(fill: rgb("#DCEAF7"))[*Prefill*],
    ),
    table.cell(rowspan: 2, align: horizon + center, fill: rgb("#EEF5FC"))[*空间结构*],
    [副本绑定], [激活专家的执行节点], [和规约根联合枚举，最小化层因果时延], [按节点累计分配服务时间选择副本，输入到达仅用于平局],
    [规约根], [本层输出及下一层输入节点], [与副本组合联合评价], [依次最小化树边数、深度、总距离和节点编号],
    table.cell(rowspan: 2, align: horizon + center, fill: rgb("#F2FAF7"))[*资源仲裁*],
    [计算仲裁], [就绪任务获得节点端口的次序], [单 Token 内按活动 rank 顺序执行同节点专家], [按 Token、执行阶段、就绪时间和任务编号排序],
    [链路仲裁], [就绪传输获得有向链路的次序], [最早可执行时间与稳定传输编号], [就绪事件按有向链路可用日历工作保持推进],
    table.cell(fill: rgb("#FFF8F1"))[*传输语义*], [分组传输策略], [消息粒度、路径及转发], [点到点最短 XY；Collective 使用最短路径树], [完整激活或局部和按树边传输，逐跳存储转发],
  ),
  caption: figure.caption(position: top, [数据流调度的五个决策轴。前两轴选择执行结构，中间两轴仲裁物理资源，分组传输策略固定消息如何进入网络。]),
) <tab:report-scheduling-axes>

=== Decode Scheduling

执行副本决定各节点承担的计算时间，规约根决定结果汇合的传输距离。Decode 调度器联合选择两者，以缩短本层的最慢执行分支。给定副本选择 $b$，节点 $n$ 上各激活专家的服务时间之和记为 $C_n(b)$。输入源节点为 $s_l$，规约根为 $u$，节点间跳数为 $h$，单跳输入与输出传输时间分别为 $t_"in"$ 和 $t_"out"$。本层的估计完成时间为

$
L(b,u)=max_(n:C_n(b)>0)[h(s_l,n)t_"in"+C_n(b)+h(n,u)t_"out"].
$ <eq:report-joint-score>

式中三项依次对应输入分发、节点内串行计算和输出规约，最大值取自参与计算的节点。规划器选择估计时间最短的方案，时间相同时优先选择分发与规约树总边数较少的方案，再按固定的节点及副本编号顺序确定结果。

搜索先绑定只有一个副本的专家，再按可选副本数从少到多处理其余专家。每选择一个副本，调度器便累加对应节点的计算时间，继续选择下一个专家。全部专家绑定后，比较所有 Mesh 节点作为规约根的评分，并更新当前最优方案。随后撤销最近一次绑定，尝试其他副本。@alg:report-decode-joint 给出这一搜索过程。

已选专家的计算时间可以给出当前分支的时延下限。后续专家加入只会增加节点工作量，若下限已超过当前最优评分，该分支便可直接剪去。下限与最优评分相等时仍继续搜索，以比较通信树边数。Mesh 的曼哈顿距离可分解为四个方向项，调度器维护各项的最大值，每次绑定只更新新增计算所在的节点。评价一个规约根只需比较这四项，节点间距离和通信树边数也预先计算并复用。

#figure(
  block(width: 100%, breakable: false)[
    #set text(size: 8.5pt, lang: "en", region: "US")
    #set align(left)
    #set par(first-line-indent: 0em, leading: 0.45em, spacing: 0em)
    #line(length: 100%, stroke: 0.5pt)
    #v(3pt)
    *Input:* Active experts and replicas; input source; replica service times; per-hop transfer times; Mesh distances.
    #v(2pt)
    *Output:* The best replica assignment and reduction root.
    #v(4pt)
    #let row(i, body, depth: 0) = (align(right)[#i], pad(left: depth * 11pt, align(left, body)))
    #grid(
      columns: (15pt, 1fr), align: (right, left), column-gutter: 6pt, row-gutter: 1.3pt,
      ..row(1, [Bind experts with one replica and accumulate their node work]),
      ..row(2, [Sort the remaining experts $V$ by increasing replica count]),
      ..row(3, [Initialize the best latency to $infinity$]),
      ..row(4, [Call *Search*$(1)$ and return the best solution]),
      ..row(5, [*procedure Search*$(i)$]),
      ..row(6, [*if* the partial latency bound exceeds the best latency *then return*], depth: 1),
      ..row(7, [*if* all experts are bound *then*], depth: 1),
      ..row(8, [*for each* Mesh node $u$ *do*], depth: 2),
      ..row(9, [Evaluate $L(b,u)$ for the current binding $b$], depth: 3),
      ..row(10, [*if* the candidate is better by latency, tree edges, and fixed ID order *then*], depth: 3),
      ..row(11, [Save the binding and root; update the best latency], depth: 4),
      ..row(12, [*end if*], depth: 3),
      ..row(13, [*end for*; *return*], depth: 2),
      ..row(14, [*end if*], depth: 1),
      ..row(15, [*for each* replica of expert $V_i$ *do*], depth: 1),
      ..row(16, [Bind the replica and update node work and the latency bound], depth: 2),
      ..row(17, [Call *Search*$(i+1)$], depth: 2),
      ..row(18, [Undo the binding and restore node work and the bound], depth: 2),
      ..row(19, [*end for*], depth: 1),
      ..row(20, [*end procedure*]),
    )
    #v(3pt)
    #line(length: 100%, stroke: 0.5pt)
  ],
  kind: "algorithm", supplement: [Algorithm],
  caption: figure.caption(position: top, [Joint Replica and Reduction-Root Search for Decode.]),
) <alg:report-decode-joint>

执行器随后按入选副本与规约根构造通信树，并在本层输出就绪后启动下一层规划。

=== Prefill Scheduling

Prefill 窗口内，各 Token 分别经历输入分发、专家计算和输出规约。多个 Token 可以同时处于不同层和不同执行阶段，其任务共同使用节点和链路。若连续激活的专家集中在少数节点，其他节点即使空闲，窗口仍需等待这些节点完成积压的计算。调度器在每个 Token 的层输入就绪时选择副本，利用多个执行位置分散计算工作，再组织该 Token 的分发与规约。

副本分派以节点累计分配的计算时间衡量负载。窗口开始时，各节点的累计时间 $W_n$ 为零，每次分配任务后累加其服务时间。对当前激活专家 $e$，调度器从可用副本所在节点集合 $R_e$ 中，选择加入本次任务后累计时间最短的节点：

$
a_e = arg min_(n in R_e)(W_n + T_(e,n)), quad W_(a_e) arrow.l W_(a_e) + T_(e,a_e).
$

其中 $T_(e,n)$ 为硬件代价模型给出的专家在节点 $n$ 上的计算服务时间。同一 Token 的专家依次分派，每次选择都更新累计时间，供后续专家选择时使用。累计时间相同时，优先选择输入预计较早到达的节点。

执行位置确定后，调度器选择连接这些节点所需树边最少的规约根。树边数相同时，依次比较最大传输跳数、总跳数和节点编号。输入从源节点沿最短路径树多播，输出沿以规约根为根的最短路径树汇合。这两棵树在本次层执行期间保持固定，共用树边上的输入只传输一次，在分支节点复制至下游。

各节点优先执行较早 Token 的就绪计算任务，同一 Token 再按计算阶段和就绪时间安排次序。不同 Token 的传输竞争同一有向链路时，按链路可用时间依次服务。一个 Token 完成本层规约后即可进入后继层，其他 Token 继续各自的计算与传输。窗口完成时间取最后一个 Token 的完成时刻。实验中的轮转基准按专家轮流选择副本，与本方法共用规约、通信树和任务执行规则。
