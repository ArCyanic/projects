#import "../components.typ": *

= Evaluation

== Experimental Setup

实验评估 DeepSeek-V3 @deepseekv32024、DeepSeek-V2-Lite @deepseekv22024 与 Qwen2-57B-A14B @qwen22024 三种模型的跨层 Dense/MoE FFN 执行链。芯片总存储容量固定为各模型权重体积的 1.5 倍，Planar 与 Vertical 的微架构参数分别按 @tab:setup[表] 中的原型系统标定。Qwen2 与 DeepSeek-V2-Lite 采用公开路由数据集 @moebeyond2025 @prefetchmlp2026 @hdmoe2025，DeepSeek-V3 采用合成路由数据；离线映射、验证择优与冻结测试分别使用互不重叠的 4,096 条路由区间（超图构建读取前 1,024 条训练路由，验证曲线每档窗口规模使用 1 个窗口，冻结测试每档规模使用 8 个窗口）。总体性能实验（@fig:cross-model[图]与 @fig:main[图]）以相同运行时策略下的全工作量均衡单副本部署为基准（记为 1），分别绘制 Decode 归一化速度（$J_D^"base" / J_D$）与相同窗口规模下的 Prefill 归一化吞吐量（$J_P^"base" / J_P$）；正文均汇报平均时延降幅。

#paper-table([Hardware Configurations. Node depth is shown for DeepSeek-V3.], (1.15fr, 1fr, 1fr),
  table.header([*Parameter*], [*Planar*], [*Vertical*]),
  [Prototype], [Jang et al. @jang2025], [3D-FPIM @lee2022],
  [Array / precision], [$128 times 512$ / W8A8], [$128 times 128$ / W5A5],
  [Mesh / node plane], table.cell(colspan: 2)[$4 times 4$ / $8192 times 16384$],
  [Depth / link BW], table.cell(colspan: 2)[460 / 0.5, 2, #box[8 GB/s]],
) <tab:setup>

== Overall Performance

#paper-figure("figures/07-cross-model-results.pdf", [Cross-Model Performance at #box[2 GB/s] and ≈20% replication. Normalized Decode speed and Prefill throughput relative to the single-copy compute-balanced baseline (1): 4,096 Decode routes and eight windows per Prefill size T32/T128/T512.]) <fig:cross-model>

*跨模型性能。* 如 @fig:cross-model[图] 所示，在 #box[2 GB/s] 链路带宽下增加约 20% 专家副本后，三种模型与两种计算读出机制组成的六组配置中，Decode 平均时延较单副本基准降低 15.18%–18.46%，Prefill 批处理时延降低 3.86%–12.61%。不同模型的专家粒度与计算读出耗时通过 Weight-Cube 统一进入映射与调度流程；六组配置中，两组终点部署选自计算均衡起点轨迹，四组选自超图起点轨迹。

#paper-figure("figures/04-main-results.pdf", [Normalized Performance Across Replica Budgets. DeepSeek-V3 validation results; baseline = the single-copy compute-balanced deployment. Columns: 0.5/2/8 GB/s. Rows: Decode speed and Prefill throughput at T32/T128/T512. P/V tracks identify the selected initial layout; Prefill uses one window per size.]) <fig:main>

*副本预算演进。* @fig:main[图] 展示了 DeepSeek-V3 在三档链路带宽下随副本预算演进的性能曲线。在 20% 终点预算下，Decode 平均时延降低 14.61%–24.59%，Prefill T512 批处理时延降低 4.44%–11.90%。在 Prefill 阶段，最初约 5% 的副本预算即取得了 T512 终点改善量的 91.65%–97.93%：新增副本分流了高频专家的并发调用，迅速削减了热点节点的峰值计算工作量 $W_C$。但在通信受限的 Planar、#box[0.5 GB/s] 配置下，由于固定最短路径树上的链路传输争用限制了并发分流的即时兑现，首个 1% 预算仅取得终点改善量的 23.62%，直至后续预算下的位置交换搜索缓解链路瓶颈后，批处理吞吐才大幅提升。

当副本预算进入 10%–20% 区间时，两阶段的边际收益出现分化。对于大窗口 Prefill（T512），全芯片节点计算负载已高度均衡：例如在 Planar、#box[2 GB/s]、20% 预算下，T512 窗口完成时间 $J_P$ 为 216.36 ms，而由最忙节点峰值计算工作量决定的资源下界 $B_"exec" = W_C$ 为 214.07 ms，完成时间相对该资源下界的间隙仅为 1.06%（全网平均计算利用率达 98.92%），因此 10%–20% 预算内的 T512 时延降幅变化仅为 0.06–0.39 个百分点。相比之下，单 Token Decode 未受全网容量饱和限制，仍可利用新增副本持续缩短跨层关键路径。

*双轨迹选择与吞吐保护。* 两条优化轨迹的选择结果体现了不同带宽下的阶段权衡。在 Planar、#box[0.5 GB/s] 的 1% 预算下，超图起点虽将 Decode 时延降低 21.50%，但共激活专家的高度聚集加剧了并发请求下的节点串行积压，导致 T512 批处理时延恶化 17.21%；框架依据回退门限剔除该候选并保留计算均衡轨迹（此时入选部署受链路传输制约，链路工作量下界 $W_L = 237.83$ ms 高于计算工作量下界 $W_C = 216.85$ ms）。而在 #box[8 GB/s] 高带宽下，跨节点传输耗时显著缩短，超图轨迹在同预算下同时降低 Decode 时延（11.48%）与 T512 批处理时延（3.05%），从而入选输出部署。

== Hardware-Aware Mapping

#paper-figure("figures/05-decode-analysis.pdf", [Single-Copy DeepSeek-V3 Test Placement. (a) Decode latency change relative to the matched layout, $100 times (J_D / J_D^"matched" - 1)$. (b) Planar 0.5/8-GB/s layouts at #box[2 GB/s]: node color shows extra co-activated experts beyond one per node (per MoE layer and trace); edge width shows bidirectional tree packets.], wide: true, placement: bottom) <fig:decode-analysis>

同一读出机制内的单副本超图布局共享同一计算均衡起点，从而隔离多副本配额分配与在线副本绑定的影响（@fig:decode-analysis[图]）。固定 #box[2 GB/s] 评价带宽时（@fig:decode-analysis[图](b)），Planar 的 #box[0.5 GB/s] 布局将高频共激活专家向网格中心聚拢（每层平均 2.37 个同节点额外共激活专家、12.94 树包跳），#box[8 GB/s] 布局则将其分散布置于全网 16 个节点（0.92 个额外专家、17.80 树包跳）。在单 Token 专家计算时间 $T_"expert"$ 固定下，这一空间位置切换转化为 $T_"node"$ 与 $T_"mesh"$ 的对冲，使 Planar 与 Vertical 在 $3 times 3$ 重放各评价带宽列中均由匹配布局取得最低实测时延（@fig:decode-analysis[图](a)）：Planar 在 #box[0.5 GB/s] 下以增加 0.30 ms 的 $T_"node"$ 换取 1.40 ms 的 $T_"mesh"$ 缩减（Decode 净时延降低 19.37%），在 #box[8 GB/s] 下则以增加 0.08 ms 的 $T_"mesh"$ 消除 0.54 ms 的 $T_"node"$（净降 22.79%；Vertical 同口径分别降低 13.36% 与 16.71%）。在约 20% 副本预算下，配额与位置联合演化延续了该权衡（Planar 在 #box[0.5 GB/s] 与 #box[8 GB/s] 下分别降低 13.83% 与 25.51%），并为运行时调度提供了分布式副本。

== Scheduling Ablation Study

#paper-figure("figures/06-scheduling-results.pdf", [Frozen ≈20% DeepSeek-V3 Test Scheduling. (a) Decode network ($T_"mesh" + T_"wait"$) and serialization ($T_"node"$) changes as percentages of baseline $J_D$ (nearest copy, source root); dashed lines fix $Delta J_D$. (b) Prefill node occupancy (hatched: completed-window region) and work/mean on Planar, #box[2 GB/s], T128 window 0.], wide: true) <fig:scheduling>

在固定 20% 终点部署上（@fig:scheduling[图](a)），仅动态迁移规约根（root-only）会改变下一层输入源 $s_(l+1)$ 及后继层就近副本选择，从而同时改变网络与节点串行耗时：在 Planar、#box[0.5 GB/s] 下，root-only 将网络耗时削减基准 $J_D$ 的 37.83%，伴随串行微增 2.65%（净时延降低 35.18%，联合规划达 37.31%）。而在 #box[8 GB/s] 下，root-only 净降幅仅为 3.80%；副本—规约根联合规划（joint）主动避开同节点共驻热点，以网络耗时微增 1.22% 换取串行耗时削减 28.20%，使净时延降低 26.98%（Vertical 同带宽下降低 29.47%）。

对于 Prefill 阶段，在共用建树与规约根选择规则下，最小累计工作量分派较逐专家轮转分派在 T32、T128 与 T512 下分别降低 11.56%–14.62%、7.50%–13.10% 与 4.30%–11.75% 的窗口完成时间。逐专家轮转忽略了跨专家共享节点的已分配负载，使不同高频专家的计算工作量在共驻节点上叠加：如 @fig:scheduling[图](b) 所示，两种策略执行完全相同的总计算工作量，而跟踪节点全局已分配工作量将峰值 $W_C$ 由 58.15 ms 压低至 53.57 ms，窗口完成时间 $J_P$ 由 63.48 ms 缩短至 55.77 ms。
