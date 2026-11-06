#import "design-report-cn.typ": design-report-cn, design-report-appendix
#import "results.typ": result, number, pct, value-range, profile-name

#show: design-report-cn.with(
  title: [三维存算一体 MoE 推理系统设计报告],
  subtitle: [权重映射与数据流调度],
  authors: (),
  date: [2026 年 10 月 13 日],
)

= 引言

#include "chapters/introduction.typ"

= 问题定义

#include "chapters/principles.typ"

= 顶层设计

#include "chapters/architecture.typ"
= 硬件抽象与代价模型

#include "chapters/detailed-hardware.typ"

= 基础设施

#include "chapters/infrastructure.typ"

= 性能分析

#include "chapters/detailed-simulation.typ"

= 权重映射

#include "chapters/detailed-mapping.typ"

= 实验评估

#include "chapters/experimental-results.typ"

= 总结

本报告研究三维存算硬件上的共享专家映射如何同时服务 Decode 结构与 Prefill 并发容量。系统从计入固定稠密层与 MoE 工作量的计算均衡单副本部署生成两个起点，在每一档复制预算内依次执行 Prefill 容量分配和 Decode 结构搜索，再按 Prefill 回退门限选择逐预算部署。

在 2 GB/s 和约 20% 额外副本预算下，DeepSeek-V3、DeepSeek-V2-Lite 与 Qwen2-57B-A14B 的独立测试覆盖 Planar 和 Vertical 六组配置。两个小模型使用公开路由，DeepSeek-V3 使用 seed0 合成路由。相对各自的全工作量均衡单副本基准，Decode 时延降低 #value-range(result.ranges.cross_decode)，Prefill 窗口完成时间降低 #value-range(result.ranges.cross_prefill)。三模型总体结果展示了有限副本在不同专家规模和共享结构下的部署收益。

三档带宽实验显示，低带宽布局通过增加局部串行压缩通信半径，高带宽布局则展开共激活专家以减少节点串行。这一结果说明，带宽决定了静态映射在通信局部性与计算分散之间的交换方向。容量放松对照展示了中心节点空间对低带宽通信局部性的限制。8–64 GB/s 扩展中，单副本搜索的串行结构变化较小，额外带宽主要缩短现有路径的传输时间。

20% 交织轨迹相对各配置的全工作量均衡单副本基准将验证集 Decode 时延降低 #value-range(result.ranges.validation.decode)，T32、T128 与 T512 分别降低 #value-range(result.ranges.validation.at("32"))、#value-range(result.ranges.validation.at("128")) 和 #value-range(result.ranges.validation.at("512"))。两个低带宽配置在全部预算点选择计算均衡路径，2/8 GB/s 的终点选择超图路径。复制持续把起点差异写入后续驻留组合，单副本赢家无法代表整条容量路径。

20% 扩展显示出两类请求不同的边际收益结构。Prefill 副本首先分流热点节点的计算工作，T512 在约 5% 预算取得终点收益的 #value-range(result.ranges.five_percent_share.at("512"))，10%–20% 再增加 #value-range(result.ranges.late.at("512"), suffix: "") 个百分点。Decode 副本则增加专家绑定与规约路径的组合，同一区间仍改善 #value-range(result.ranges.late.decode, suffix: "") 个百分点。这组差异解释了每档预算先补充 Prefill 服务位置、再搜索 Decode 结构的顺序。

调度消融进一步表明，低带宽 Decode 的主要收益来自动态规约根；20% 容量在高带宽下提供了更丰富的驻留组合。Prefill 在固定规约与通信树下采用最小累计工作量分派，相对轮转 baseline，DeepSeek-V3 的 T32 时延下降 #value-range((calc.min(..result.dataflow.map(r => r.prefill.at("32"))), calc.max(..result.dataflow.map(r => r.prefill.at("32")))))，T512 下降 #value-range((calc.min(..result.dataflow.map(r => r.prefill.at("512"))), calc.max(..result.dataflow.map(r => r.prefill.at("512")))))。

#set text(size: 7.5pt)
#bibliography("references.bib", title: [参考文献], style: "association-for-computing-machinery")

#design-report-appendix[
  = 硬件代价模型推导 <appendix:hardware-cost>
  #include "appendices/hardware-cost.typ"

  = 部署泛化与路由对照 <appendix:extended-experiments>
  #include "appendices/extended-experiments.typ"
]
