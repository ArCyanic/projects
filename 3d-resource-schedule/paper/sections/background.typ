#import "../components.typ": *

= Background and Motivation

== 3D CIM for MoE Inference

三维存内计算（3D CIM）通过垂直堆叠多层存储阵列实现全模型专家权重的片上常驻与原位模拟乘加 @buchel2025 @jang2025 @lee2022。在本文关注的 3D CIM 节点组织中，垂直堆叠的多层阵列共享外围驱动、字线控制与模数转换（ADC）读出电路，同一计算单元在任意时刻仅能激活单个权重算子执行乘加，构成单任务互斥执行约束。多个计算节点通过二维网格（2D Mesh）片上网络互联：分布于不同节点的活跃专家可并行计算，但跨节点的数据分发与结果汇聚会产生与传输跳数相关的网络延迟；共驻于同一节点的活跃专家则须在节点内串行执行。

混合专家模型（MoE）通过门控网络为每个 Token 动态选择 Top-$k$ 专家，并结合共享专家参与前馈层计算 @deepseekmoe2024 @deepseekv32024。单层执行时，输入激活从当前源节点分发至各活跃专家所在节点，各节点完成本地乘加后，结果沿片上网络汇聚为层输出并作为下一层输入源。在负载形态上，Decode 阶段逐 Token 串行推进，单步时延受限于包含输入分发、节点计算与结果汇聚的最慢执行分支；Prefill 阶段并发处理窗口内的多个输入 Token，高频专家被反复调用，易在驻留节点上造成串行计算积压与负载倾斜。

== Related Work and Motivation

#include "../tables/framework-comparison.typ"

#paper-figure("figures/03-mapping-scheduling.drawio.pdf", [Motivating Example. A $2 times 2$ region of a $4 times 4$ Mesh with $tau$ per hop and $2 tau$ per expert. Executing $E_2$ at N4 and reducing at N5 lowers layer latency from $6 tau$ to $4 tau$.]) <fig:mechanism>

*已有支持。* @tab:framework-comparison[表] 对比了代表性存内计算编译框架与 3D MoE 系统。在编译与模拟工具链方面，PUMA @puma2019、PIMCOMP @pimcomp2023、CIM-MLC @cimmlc2024、CIMFlow @cimflow2025 与多核映射方法 @liu2025 支持二维阵列上的权重复制、核间映射与静态操作流生成，但均针对二维阵列与静态计算图建模，未涵盖三维堆叠容量约束、Token 级动态路由及运行时副本选择。在 3D CIM 架构与 MoE 部署方面，3D-FPIM @lee2022 与 Jang 等人 @jang2025 分别构建了垂直电容累加与平面数字规约的 3D NAND 原位计算微架构；面向 MoE 负载，3D AIMC @buchel2025 将专家矩阵分块部署至堆叠阵列并通过 Token 级操作图模拟评估单层互斥激活下的执行时延，OPTIMEX @sharma2025 则基于激活统计搜索异构 SRAM/ReRAM 存储层中的专家投影放置。然而，这两类 3D MoE 方案均采用单副本静态驻留，未支持多副本冗余部署与运行时动态副本选择；近存 MoE 与推荐系统（Stratum @pan2025、ExFlow @exflow2024、UpDLRM @updlrm2024）亦未考虑 3D CIM 节点互斥串行与跨层汇聚位置传递。

*具体执行。* @fig:mechanism[图] 展示了 $4 times 4$ Mesh 的 $2 times 2$ 局部区域在固定权重驻留下的单层执行过程。设单跳传输时间为 $tau$，单专家本地执行时间为 $2 tau$。当前层输入位于 N0，门控路由激活专家 $E_1$、$E_2$ 与 $E_3$；其中 $E_1$ 与 $E_2$ 共驻 N1，$E_2$ 在 N4 设有额外副本，$E_3$ 驻留 N5。基准方案采用就近副本绑定并在源节点 N0 汇聚：输入于 $tau$ 到达 N1，$E_1$ 与 $E_2$ 在 N1 串行计算至 $5 tau$，结果经 1 跳返回 N0，单层完成时间为 $6 tau$。若将 $E_2$ 分派至 N4 副本，输入于 $tau$ 到达 N1 与 N4，两专家并行计算并于 $3 tau$ 完成；同时选择 N5 作为树形规约根节点（下文简称规约根，Reduction Root），N1 与 N4 的结果各经 1 跳于 $4 tau$ 到达 N5，与 N5 本地在 $4 tau$ 完成的 $E_3$ 结果合并，完成时间缩短至 $4 tau$。规约根不仅决定当前层汇聚耗时，还直接成为下一层输入分发的源节点；仅按当前层就近汇聚可能使层输出偏离下一层活跃专家，增加后继层分发跳数。

*设计需求。* 在跨层 FFN 执行链中实现上述收益，首先需量化副本驻留与本地计算耗时：在 N4 增设 $E_2$ 副本受制于节点三维堆叠容量，且算子分块尺寸与读出方式共同决定单专家本地执行时间，需建立统一的硬件抽象与代价模型（§3）。运行时，动态路由使各层活跃专家组合随 Token 变化，同节点串行、共享有向链路争用与规约根（如 N5）向下一层输入源的位置传递相互交织，需构建跨层时序执行模型与瓶颈分析器（§4.2）。同时，离线副本配置与空间布局框定了在线绑定与汇聚选择的可达范围，且同一权重部署须兼顾单 Token Decode 关键路径与多 Token Prefill 并发吞吐，需协同设计离线交替映射与在线数据流调度算法（§4.3）。
