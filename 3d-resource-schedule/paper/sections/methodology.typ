#import "../components.typ": *

= Inference Framework

== Overview

#paper-figure("figures/01-framework.drawio.pdf", [Deployment and Execution Framework. At each budget, weight mapping adds expert replicas and swaps their node locations. The selected deployment supports both runtime policies. The Performance Profiler evaluates execution latency and throughput, identifies bottlenecks, and provides layer, expert, node, and link diagnostics. Dashed arrows indicate budget progression and latency feedback.], wide: true) <fig:framework>

@fig:framework[图] 展示了面向 3D CIM 的 MoE 部署与执行协同框架。框架接收模型结构、专家路由统计与硬件配置，允许同一专家在多个计算节点常驻副本，为每次专家激活提供多个可选执行位置。在离线阶段，空间编译器（§4.2.1）将算子权重转换为三维权重块并检验节点装箱可行性；离线权重映射（§4.3.1）在递增副本预算下交替执行热点副本扩充与同层位置交换，调用推理执行模块（§4.2.2）与性能分析器（§4.2.3）获取候选部署的时延与瓶颈反馈，筛选出兼顾 Prefill 吞吐与 Decode 时延的权重部署。在在线阶段，数据流调度器（§4.3.2）基于选定部署与实时 Token 路由，逐层规划执行副本与规约根，驱动跨层推理执行并输出端到端性能与诊断结果。

== Framework Design

=== Weight Deployment

空间编译器根据算子权重矩阵形状与硬件配置生成 Weight-Cube。矩阵输入输出维度决定驻留参数规模，节点的二维平面尺寸与存储深度约束单个权重块的三维边界。当算子矩阵超出计算单元的平面边界时，编译器对矩阵分片并沿深度叠放，将二维矩阵转换为可在节点内执行的 Weight-Cube。

矩阵沿输入维分片时，各分片结果在节点内相加合并；沿输出维分片时，结果按输出区间拼接，保持原算子的输入输出维度。编译器依据第 3 章的模型确定三维尺寸 $(H_c,W_c,D_c)$ 与本地执行时间 $T_c$。在 Vertical 配置下，编译器比较候选深度的位线模拟累加与数字合并耗时，选择使 $T_c^"V"$ 最小的累加深度 $d$。Gate/Up 与 Down 投影的权重块共同构成一个完整的专家副本，投影间的门控中间结果留在节点内部处理，仅专家整体输入与输出通过片上网络传输。

离线权重映射确定各专家副本的驻留节点后，空间编译器将对应权重块装入目标节点，检验三维几何边界与非重叠约束并分配坐标；离线容量可行性检查与最终部署生成共用同一装箱过程。生成的部署记录各副本的驻留节点、块尺寸、空间坐标、累加深度与本地执行时间，供运行时按路由调用。

=== Inference Execution

*共同模型。* 权重部署与当前路由确定待执行的活跃专家，硬件模型给出计算时间 $T_e$ 及输入输出字节数。输入沿最短路径多播树送达选定的执行节点，重合有向链路仅传输一次并在分支节点复制数据；同节点活跃专家按互斥约束串行计算；结果沿最短路径规约树汇聚至规约根形成层输出，该规约根随即成为下一层输入源。有向 Mesh 链路独立占用，单跳时间由通信载荷与带宽确定，同链路上的传输串行执行。

*Decode 时延计算。* Decode 阶段单 Token 按层推进，同节点专家的计算时间直接累加。MoE 层的输入与输出为同维度向量，单跳传输时间相等（$t_"in"=t_"out"$）。搜索候选方案时，给定副本选择 $a$（专家 $e$ 绑定至节点 $a_e$）与候选规约根 $u$，框架按无链路争用的单分支最大耗时计算候选评分：

$
L(a,u)=max_(n in {a_e}) [h(s,n)t_"in"
+sum_(e:a_e=n)T_e+h(n,u)t_"out"],
$ <eq:decode-plan>

其中 $s$ 为当前层输入源，$h(dot,dot)$ 为网格最短跳数。确定入选方案 $(a^*,u^*)$ 后，框架通过关键路径递推计算包含共享链路争用的完整时延 $J_D$：由于专家计算时间 $T_e>0$，且结果到达任意链路起点前已历经输入传输、计算与前序结果传输，其路程不短于输入到达该起点的最短路径，故共享有向链路上的输入传输必先于结果传输启动。框架据此由跳数确定输入到达时间，并将共享链路上的输入完成时间加入结果传输的前驱关系；各节点收齐本地与子分支结果后向父节点传输，按树形依赖递推得到计入链路等待的完整时延 $J_D$，并将层完成时间与规约根位置传递至下一层。

*Prefill 模拟。* Prefill 阶段多个 Token 并发使用计算节点与链路，任务的启动时间随并发状态变化。离散事件模拟器接收所选副本与规约根，维护任务依赖及节点、链路的可用时间日历，推进计算与传输完成事件。就绪计算任务依次按 Token 编号、计算阶段与就绪时间仲裁；任务完成后释放后继任务并更新资源日历，最终输出窗口完成时间 $J_P$ 及资源占用记录。

=== Performance Profiler

性能分析器接收 Decode 完整时延与 Prefill 资源记录，提取瓶颈指标并向离线映射提供评价反馈。在 Decode 阶段，分析器以候选评分中的最慢分支为基础，将完整时延 $J_D$ 分解为四项：

$
J_D=T_"expert"+T_"node"+T_"mesh"+T_"wait".
$ <eq:decode-parts>

其中 $T_"expert"$ 为单专家基础计算时间，$T_"node"$ 为同节点其余活跃专家叠加的串行计算时间，$T_"mesh"$ 为最慢分支的无争用网格传输时间；完整时延与前三项之和的差值为集合通信等待时间 $T_"wait"$，量化规约分支同步与共享链路争用引入的延迟。由于带宽变化可能切换最慢分支，分析器支持在统一评价带宽下交叉重放不同部署，分离布局在传输跳数与节点串行上的差异。

在 Prefill 阶段，令窗口内最大节点累计计算工作量为 $W_C$，最大有向链路传输工作量为 $W_L$，单 Token 依赖链下界为 $L_"dep"$，分析器构建批处理执行下界：

$
B_"exec"=max(W_C,W_L,L_"dep"),
quad J_P>=B_"exec".
$ <eq:prefill-bound>

副本扩充与在线分流通过削减 $W_C$ 与 $W_L$ 降低下界 $B_"exec"$；差值 $J_P-B_"exec"$ 反映依赖同步、资源争用及流水线填充排空的调度延迟。当窗口并发度增大使全网节点平均计算利用率趋近饱和时，完成时间渐近逼近由总计算工作量决定的计算下界。

#include "mapping.typ"
#include "scheduling.typ"
