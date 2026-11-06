#import "../components.typ": *

=== Dataflow Scheduling

权重部署确定后，专家 $e$ 驻留于候选节点集合 $cal(R)_e$。运行时，门控网络确定每个 Token 激活的专家集合；调度器从 $cal(R)_e$ 中选择本次调用的执行节点 $a_e in cal(R)_e$，将输入从当前源节点 $s$ 分发至这些位置；各节点完成计算后，将结果送至所选规约根 $u$ 汇聚成层输出，节点 $u$ 随即成为下一层的输入源。调度器逐层重复该过程，将静态权重部署组织为随路由变化的数据流。

沿此数据流，执行副本选择 $a={a_e}$ 与规约根选择 $u$ 共同决定单层完成时间：副本位置 $a_e$ 决定输入传输目的地与各节点的串行计算分布，规约根 $u$ 决定结果传输距离与下一层输入起点。@tab:scheduling-dimensions[表] 对照了 Decode 与 Prefill 的副本绑定和规约根策略；两者采用共同的通信树、任务优先级与链路推进规则（§4.2.2）。

#paper-table([Dataflow Scheduling Policies], (0.95fr, 1.15fr, 1.15fr),
  table.header([*Decision / rule*], [*Decode*], [*Prefill*]),
  [Replica binding], table.cell(rowspan: 2, align: center + horizon)[Joint min. $L(a,u)$], [Min. $W_n+T_(e,n)$],
  [Reduction root], [Min. tree edges],
  [Collective trees], table.cell(colspan: 2)[Shortest-path trees],
  [Task order], table.cell(colspan: 2)[Token → stage → ready time],
  [Link calendar], table.cell(colspan: 2)[Directed-link availability],
) <tab:scheduling-dimensions>

*Decode 联合规划。* Decode 阶段单 Token 按层推进，当前层输出就绪后方可启动下一层。调度器使用 §4.2.2 的候选评分 $L(a,u)$（式 @eq:decode-plan）联合比较执行副本与候选规约根，选取最慢分支评分最小的组合 $(a^*,u^*)$。由于 $L(a,u)$ 同时计入跳数传输时间与同节点串行计算时间，调度器在同一评分准则下随带宽与共驻冲突选中不同方案：单跳传输延迟较高时，靠近输入源与规约根的副本因通信跳数更少而使 $L(a,u)$ 更小；同节点多专家串行耗时超过跨节点传输延迟时，将活跃专家分派至其他节点的可用副本可降低 $L(a,u)$，从而入选并实现多节点并行计算。随后框架调用关键路径计算得到入选方案的完整时延 $J_D$，并将规约根 $u^*$ 作为下一层输入源。

*Prefill 累计工作量分派与规约汇聚。* Prefill 阶段窗口内多个 Token 并发执行，高频专家被反复调用。调度器在窗口内动态累计各节点已分配的计算时间 $W_n$，每次为活跃专家 $e$ 选择叠加当前任务后累计工作量最小的候选节点并立即更新累计量 @hdmoe2025：

$
a_e=arg min_(n in cal(R)_e)(W_n+T_(e,n)), quad W_(a_e) arrow.l W_(a_e)+T_(e,a_e).
$ <eq:prefill-bind>

同一 Token 内的专家按序分派并读取更新后的累计量，使计算分散至可用副本；工作量相同时依次按预计输入到达时间与节点编号仲裁。本层执行节点集合确定后，调度器选择优先减少规约树有向边数、并在并列候选中缩短最远结果传输距离的节点作为规约根 $u$。输入沿分发树送达执行节点，结果沿规约树汇聚至 $u$ 并作为下一层输入源，跨 Token 资源争用由事件模拟器推进。
