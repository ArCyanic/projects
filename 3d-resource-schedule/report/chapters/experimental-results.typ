#import "../results.typ": result, number, pct, value-range, profile-name, performance-ratio
#let zero-copy = json("/report/data/zero-copy.json")
#let high-bandwidth = json("/report/data/high-bandwidth.json")

本章评估有限副本如何同时服务 Decode 与 Prefill。实验先在 DeepSeek-V3、DeepSeek-V2-Lite 和 Qwen2-57B-A14B 上比较约 20% 副本预算的总体收益，再围绕 DeepSeek-V3 分析三档 Mesh 带宽、0%–20% 容量演化、物理时延分解与调度消融。

== 实验设置

=== 实验输入

@fig:experiment-preprocessing 展示 DeepSeek-V3 到实验输入的转换。静态分支将模型配置展开为稠密 MLP、路由专家与共享专家的 FFN 算子，统一矩阵方向并生成硬件权重块；动态分支提供逐 Token 路由，并由训练区间统计专家需求、共激活和跨层转移。

#figure(
  image("/assets/figures/experiment-preprocessing.pdf", width: 100%),
  caption: [DeepSeek-V3 合成输入的实验预处理流程。模型计算图确定静态权重块和依赖，路由轨迹确定逐 Token 激活及映射统计。两类输入共同进入部署构造和物理评价。],
) <fig:experiment-preprocessing>

机制分析的主模型为 DeepSeek-V3：包含 3 个稠密层与 58 个 MoE 层；每个 MoE 层包含 1 个共享专家和 256 个路由专家，每个 Token 激活 8 个路由专家。主题相关合成路由包含 16 个主题簇；每层从当前主题簇抽取 6 个专家，再按 $alpha=1.2$ 的 Zipf 分布抽取 2 个背景专家。主题在层间保持局部相关，使路由同时具有热点和跨层状态结构。总体实验同时覆盖使用公开路由的 DeepSeek-V2-Lite 和 Qwen2-57B-A14B，模型规格见 @tab:cross-model-specifications。DeepSeek-V2-Lite 的 Decode 路由来自 PrefetchMLP，Prefill 路由来自 MoE-Beyond；Qwen2 路由来自 HD-MoE。

DeepSeek-V3 生成器共输出 40,960 条路由。三模型均按路由索引使用三个互不重叠的 4,096 条区间：`[0,4096)` 用于基础映射、复制动作和位置搜索，`[4096,8192)` 用于逐预算候选选择与结构分析，`[8192,12288)` 用于冻结部署的最终评价。

=== 硬件空间配置

主实验同时使用 Planar 与 Vertical 两种计算配置。16 个 Sub-Cube 组成 $4 times 4$ Mesh，DeepSeek-V3 每个节点的逻辑空间为 $8192 times 16384 times 460$，全系统物理容量按模型权重体积的 1.5 倍配置。实际可用副本数还受稠密权重占用、逐节点装箱和完整专家块取整共同限制。@tab:experiment-hardware-profile 给出进入装箱、映射与评价器的 DeepSeek-V3 硬件参数。

#figure(
  table(
    fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
    columns: (0.9fr, 1.08fr, 0.58fr, 1.45fr, 1.0fr, 0.92fr),
    align: (left, left, center, center, center, center),
    table.header(
      table.cell(fill: rgb("#DCEAF7"))[*配置*],
      table.cell(fill: rgb("#DCEAF7"))[*计算与精度*],
      table.cell(fill: rgb("#DCEAF7"))[*Mesh*],
      table.cell(fill: rgb("#DCEAF7"))[*节点逻辑空间*],
      table.cell(fill: rgb("#DCEAF7"))[*局部 MVM*],
      table.cell(fill: rgb("#DCEAF7"))[*带宽*],
    ),
    table.cell(fill: rgb("#F5F8FC"))[Planar], [ICCD / W8A8], [$4 times 4$], [$8192 times 16384 times 460$], [$128 times 512$], [`0.5/2/8`],
    table.cell(fill: rgb("#FFF8F1"))[Vertical], [3D-FPIM / W5A5], [$4 times 4$], [$8192 times 16384 times 460$], [$128 times 128$], [`0.5/2/8`],
  ),
  caption: figure.caption(position: top, [主实验的三维资源空间与硬件配置。带宽单位为 GB/s。]),
) <tab:experiment-hardware-profile>

DeepSeek-V3 路由专家经存算编译器映射后生成如 @tab:report-compiled-weight-cubes 所示的标准权重几何块。Planar 架构采用单层平面二维存储（$D_w = 1$），Vertical 架构通过深度内并行切片组织为多层三维结构（$D_w = 7, 4$）；*几何尺寸同时决定了单节点的装箱容量与硬件本地 MVM 服务耗时。*

#figure(
  table(
    fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
    columns: (0.9fr, 1.05fr, 1.5fr, 0.75fr, 1.05fr),
    align: (left, left, center, center, right),
    table.header(
      table.cell(fill: rgb("#DCEAF7"))[*配置*],
      table.cell(fill: rgb("#DCEAF7"))[*矩阵块*],
      table.cell(fill: rgb("#DCEAF7"))[*几何尺寸 $H_w times W_w times D_w$*],
      table.cell(fill: rgb("#DCEAF7"))[*精度*],
      table.cell(fill: rgb("#DCEAF7"))[*服务时间*],
    ),
    table.cell(fill: rgb("#F5F8FC"))[Planar], [`gate_up`], [$7168 times 4096 times 1$], [W8A8], [$7288 " ns"$],
    table.cell(fill: rgb("#F5F8FC"))[Planar], [`down`], [$2048 times 7168 times 1$], [W8A8], [$5252 " ns"$],
    table.cell(fill: rgb("#FFF8F1"))[Vertical], [`gate_up`], [$1024 times 4096 times 7$], [W5A5], [$8261 " ns"$],
    table.cell(fill: rgb("#FFF8F1"))[Vertical], [`down`], [$512 times 7168 times 4$], [W5A5], [$7143 " ns"$],
  ),
  caption: figure.caption(position: top, [DeepSeek-V3 路由专家经硬件编译生成的标准权重块。]),
) <tab:report-compiled-weight-cubes>

=== 仿真评测环境

目标系统时延由第 4 章定义的硬件服务时间、节点计算资源、Mesh 链路日历、多播与规约规则进行纳秒单位的离散事件重放。当前正式批次为 #raw("build/dac-paper-full-workload/")。DeepSeek-V3 与 DeepSeek-V2-Lite 的新搜索在 Linux 服务器上完成，使用 128 个物理核心及其 SMT 线程，按 8 组、每组 32 worker 执行；Python 版本为 3.14.6。Qwen2 与全工作量单副本比较基线经过初始化核验后复用。

Decode 对每条路由从空闲资源开始执行，报告平均时延、P95、关键路径串行专家数 $N_"serial"$ 与关键路径总跳数 $N_"hop"$。Prefill 评价 32、128 和 512 个 Token 的窗口完成时间，并在机制分析中使用节点工作量与瞬时计算占用。验证曲线每种规模使用一个窗口，冻结测试和调度消融每种规模使用八个窗口。

收益比较图表以相应基线为 1，Decode 使用基线时延与当前时延之比表示归一化速度，Prefill 使用相同窗口规模下基线与当前完成时间之比表示归一化吞吐量。

@tab:mainline-runtime 汇总了 0%–20% 连续预算区间内（共 21 个预算档位）十二条 DeepSeek-V3 搜索路径的累计搜索与物理评测时间。

#figure(
  table(
    fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
    columns: (1.0fr, 0.8fr, 1.25fr, 1.25fr),
    align: (left, right, right, right),
    table.header([*配置*], [*带宽*], [*计算均衡路径*], [*超图路径*]),
    ..result.runtime.map(row => (
      [#profile-name(row.profile)], [#number(row.bandwidth)],
      [#number(row.balanced) s], [#number(row.hypergraph) s],
    )).flatten(),
  ),
  caption: figure.caption(position: top, [当前全工作量初始化批次的 DeepSeek-V3 0%–20% 逐预算累计运行时间，单位为秒，带宽单位为 GB/s。]),
) <tab:mainline-runtime>

十二条完整路径的单条累计运行时间为 #value-range(result.runtime_range, suffix: "") s，合计 #number(result.runtime_sum_seconds / 3600) h。本次包含 20 条新路径、评价、机制分析与汇总的服务器批次历时 #number(result.batch_minutes) min。

#include "cross-model-results.typ"

== 带宽条件下的单副本映射机制

单副本部署为每个 MoE 专家提供一个执行位置。将共激活专家放在近邻节点可以缩短分发与规约路径，同节点专家则需要串行计算。分散专家可以增加并行执行，同时延长通信距离。本节先比较三种放置方法，再通过固定带宽重放、容量放松和高带宽扩展分析这些取舍。

=== 状态感知超图的结构收益

@fig:zero-copy-mapping-comparison 比较轮转映射、全工作量计算均衡映射和状态感知超图映射。轮转映射按专家顺序分配节点，计算均衡映射依据稠密层与 MoE 的计算工作量放置专家，超图从计算均衡布局出发优化共激活串行、Mesh 跳数与跨层汇合位置。三组均使用 Planar 配置和相同验证路由。

#figure(
  image("/assets/figures/zero-copy-mapping-comparison.pdf", width: 100%),
  supplement: [Figure],
  caption: [Single-Copy Mapping Comparison on Planar. Filled circles and open diamonds show normalized Decode speed using mean and P95 latency, with the full-workload compute-balanced deployment as baseline (1). All methods use the same 4,096 validation routes.],
) <fig:zero-copy-mapping-comparison>

超图在 0.5/2/8 GB/s 下分别降低 Decode 平均时延 #pct(result.single_copy.at(0).mean_gain)/#pct(result.single_copy.at(1).mean_gain)/#pct(result.single_copy.at(2).mean_gain)，P95 同向下降。轮转映射仅按数量分散专家，计算均衡进一步考虑激活需求，超图再调整最慢分支上的计算与通信关系。

=== 跨带宽结构量的评价偏移

第 6 章用串行结构参照 $R_"serial"$ 和通信结构参照 $R_"hop"$ 建立统一坐标。两者投影到目标硬件后得到结构参照延迟 $J_"ref"$，候选布局相对它的差距记为 $G_"ref"$：

$
J_"ref" = op("Proj")_(theta_"hw")(R_"serial", R_"hop"),
quad
G_"ref" = frac(J_D, J_"ref") - 1.
$

@tab:zero-copy-three-bandwidth-structure 汇总三档带宽下的结构量与物理时延，并加入解除逐节点容量限制后的超图结果。容量放松对照从相同全工作量均衡布局出发，保持路由与计算、通信参数，允许专家向更多集中位置移动。

#figure(
  table(
    fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
    columns: (0.6fr, 1.35fr, 0.68fr, 0.68fr, 1.08fr, 0.68fr),
    align: (right, left, right, right, right, right),
    table.header([*GB/s*], [*Mapping*], [*$N_"serial"$*], [*$N_"hop"$*], [*Decode Speed*], [*$G_"ref"$*]),
    ..zero-copy.bandwidths.pairs().map(((key, methods)) => {
      let bandwidth = float(key)
      let reference = methods.at("compute-balanced").structure
      (
        [#number(bandwidth)], [Structural reference],
        [#number(reference.serialization_heuristic_reference_count)], [#number(reference.communication_reference_hops)],
        [#number(methods.at("compute-balanced").decode_mean_ns / reference.structural_reference_latency_ns, digits: 3)], [0%],
        ..(("compute-balanced", "Compute-balanced"), ("capacity-constrained-hypergraph", "Hypergraph: constrained"), ("capacity-relaxed-hypergraph", "Hypergraph: relaxed")).map(((name, label)) => {
          let values = methods.at(name)
          (
            [#number(bandwidth)], [#label],
            [#number(values.structure.critical_serialization_count)], [#number(values.structure.critical_hops)],
            [#number(methods.at("compute-balanced").decode_mean_ns / values.decode_mean_ns, digits: 3)],
            [#pct(100 * (values.decode_mean_ns / values.structure.structural_reference_latency_ns - 1))],
          )
        }).flatten(),
      )
    }).flatten(),
  ),
  supplement: [Table],
  caption: figure.caption(position: top, [Single-Copy Structure and Normalized Decode Speed on Planar (Compute-Balanced Baseline = 1). Constrained and capacity-relaxed searches share the full-workload initialization, 1,024 training routes, and 4,096 validation routes.]),
) <tab:zero-copy-three-bandwidth-structure>

超图在 0.5 GB/s 下把关键跳数从 #number(result.single_copy.at(0).structure.baseline.hops) 压到 #number(result.single_copy.at(0).structure.hypergraph.hops)，在 8 GB/s 下把关键串行从 #number(result.single_copy.at(2).structure.baseline.serial) 压到 #number(result.single_copy.at(2).structure.hypergraph.serial)。跨带宽比较最终布局时，低带宽布局的关键跳数为 #number(result.single_copy.at(0).structure.hypergraph.hops)，高带宽布局为 #number(result.single_copy.at(2).structure.hypergraph.hops)。这些结构量同时受到布局与评价带宽的影响。

结构量实际描述的是每层最慢分支。一个 Token 激活的专家分布在多个节点上，每个节点分支都要经历输入分发、本地计算与输出规约；其中完成最晚的节点决定该层时延。报告的 $N_"serial"$ 和 $N_"hop"$ 只统计这个关键节点上的串行专家数与往返跳数。带宽改变每跳时间后，完成最晚的节点也会改变：低带宽更容易由远距离通信分支主导，高带宽更容易由同节点计算拥塞分支主导。

因此结构量由布局 $X$ 和评价带宽 $b$ 共同决定，应写成 $S(X;b)$。对候选节点 $i$，关键完成时间为

$
C_i(b)=h_("in",i) tau_("in")(b)+W_i+h_("out",i) tau_("out")(b),
quad i^*(b)=op("argmax")_i C_i(b).
$

@tab:zero-copy-three-bandwidth-structure 测量的是两个布局—带宽联合系统：$S(X_(0.5);0.5)$ 与 $S(X_8;8)$。两个系统选择了不同的关键节点，结构量同时反映布局变化和最慢分支的切换。固定评价带宽后，才能单独观察布局对通信距离与节点串行的调整。

=== 固定带宽下的结构交换

要单独观察部署本身的取舍，两个部署必须使用同一套每跳时间重新评价。@tab:zero-copy-bandwidth-cross-replay 分别固定 0.5 GB/s 与 8 GB/s，比较相同总复制预算的两份 20% 入选部署，差异来自副本数量分配及位置。

#figure(
  table(
    fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
    columns: (0.8fr, 1.15fr, 0.85fr, 0.85fr, 1.3fr),
    align: (right, left, right, right, right),
    table.header([*GB/s*], [*Layout BW*], [*$N_"serial"$*], [*$N_"hop"$*], [*Decode Speed*]),
    ..result.cross_replay.map(row => (
      [#number(row.bandwidth)],
      [#number(row.layout_bandwidth) #if row.bandwidth == row.layout_bandwidth { [(Matched)] } else { [(Mismatched)] }],
      [#number(row.serial)], [#number(row.hops)],
      [#number(result.single_copy.find(r => r.bandwidth == row.bandwidth).baseline.mean_ns / (row.latency_ms * 1e6), digits: 3)],
    )).flatten(),
  ),
  caption: figure.caption(position: top, [Cross-Bandwidth Replay of Selected 20% Deployments. Decode speed is normalized to the compute-balanced single-copy baseline at each evaluation bandwidth. All results use validation routes; bandwidth is in GB/s.]),
) <tab:zero-copy-bandwidth-cross-replay>

#let low-matched = result.cross_replay.at(0)
#let low-mismatched = result.cross_replay.at(1)
#let high-mismatched = result.cross_replay.at(2)
#let high-matched = result.cross_replay.at(3)

固定在 0.5 GB/s 后，低带宽部署把关键跳数从错配部署的 #number(low-mismatched.hops) 压到 #number(low-matched.hops)，同时接受 #number(low-matched.serial) 对 #number(low-mismatched.serial) 的更多串行，最终时延降低 #pct(100 * (1 - low-matched.latency_ms / low-mismatched.latency_ms))。固定在 8 GB/s 后，交换方向反转：高带宽部署把串行从 #number(high-mismatched.serial) 减到 #number(high-matched.serial)，即使跳数从 #number(high-mismatched.hops) 增至 #number(high-matched.hops)，时延仍降低 #pct(100 * (1 - high-matched.latency_ms / high-mismatched.latency_ms))。低带宽布局主动增加串行以缩短通信，高带宽布局则增加通信距离以减少串行。

*带宽属于映射问题本身。目标带宽决定了静态部署在通信局部性与计算并行性之间的取舍。*

=== Node Capacity and Communication Locality

容量放松实验沿用单副本和同一全工作量初始化，解除每个节点的 MoE 驻留数量上限，以观察可用空间对通信局部性的影响。@tab:zero-copy-three-bandwidth-structure 同时给出受限与放松结果。低带宽下，共激活专家向输入与规约位置附近集中，计算串行随之增加，传输跳数则减少。

#let low-capacity = zero-copy.bandwidths.at("0.5")
#let constrained = low-capacity.at("capacity-constrained-hypergraph")
#let relaxed = low-capacity.at("capacity-relaxed-hypergraph")
在 0.5 GB/s 下，解除容量上限后，关键跳数从 #number(constrained.structure.critical_hops) 变为 #number(relaxed.structure.critical_hops)，关键串行数从 #number(constrained.structure.critical_serialization_count) 变为 #number(relaxed.structure.critical_serialization_count)，Decode 平均时延降低 #pct(100 * (1 - relaxed.decode_mean_ns / constrained.decode_mean_ns))。布局通过接受更多本地串行计算，缩短输入分发与输出规约距离。

#figure(
  image("/assets/figures/zero-copy-hypergraph-heatmaps.pdf", width: 100%),
  supplement: [Figure],
  caption: [MoE Node Occupancy and Training Compute Work on Planar at 0.5 GB/s. Columns compare compute-balanced, capacity-relaxed hypergraph, and capacity-constrained hypergraph layouts from the same full-workload initialization. Each row shares one color scale.],
) <fig:zero-copy-hypergraph-heatmaps>

#let center = (5, 6, 9, 10)
#let center-share = 100 * center.map(i => relaxed.node_occupancy.at(i)).fold(0, (a, b) => a + b) / relaxed.node_occupancy.fold(0, (a, b) => a + b)
@fig:zero-copy-hypergraph-heatmaps 展示了这次移动的空间分布。容量放松布局将 #pct(center-share, digits: 1) 的专家放在 Mesh 中心四个节点，最多一个节点容纳 #number(calc.max(..relaxed.node_occupancy), digits: 0) 个专家。受限布局中各节点必须满足物理驻留上限，部分专家转移到更远的位置。节点容量由此限制了低带宽布局压缩通信距离的程度。

#let mid-capacity = zero-copy.bandwidths.at("2.0")
在 2 GB/s 下，容量放松带来的平均时延改善缩小到 #pct(100 * (1 - mid-capacity.at("capacity-relaxed-hypergraph").decode_mean_ns / mid-capacity.at("capacity-constrained-hypergraph").decode_mean_ns))。8 GB/s 的受限与放松布局取得相同的结构量和时延。高带宽布局更倾向于分散共激活专家，中心节点的可用空间对通信距离的限制随之减弱。

=== High-Bandwidth Limits

高带宽扩展从同一全工作量均衡单副本布局出发，在 16、32 和 64 GB/s 下分别使用 1,024 条训练路由重新运行超图搜索，并以相同的 4,096 条验证路由评价。@tab:zero-copy-high-bandwidth-audit 将这些结果与 8 GB/s 的当前单副本部署比较。

#figure(
  table(
    columns: (0.68fr, 0.78fr, 0.78fr, 0.98fr, 0.72fr),
    align: (right, right, right, right, right),
    table.header([*GB/s*], [*$N_"serial"$*], [*$N_"hop"$*], [*Decode Speed*], [*$G_"ref"$*]),
    ..high-bandwidth.map(row => (
      [#number(row.bandwidth)], [#number(row.serial)], [#number(row.hops)],
      [#number(row.baseline_mean_ns / row.mean_ns, digits: 3)],
      [#pct(100 * (row.mean_ns / row.reference_ns - 1))],
    )).flatten(),
  ),
  supplement: [Table],
  caption: figure.caption(position: top, [High-Bandwidth Single-Copy Search on Planar. Decode speed is normalized to the compute-balanced baseline at each bandwidth (1). All searches share the full-workload initialization, 1,024 training routes, and 4,096 validation routes.]),
) <tab:zero-copy-high-bandwidth-audit>

8–64 GB/s 下，关键串行数保持在 #value-range((calc.min(..high-bandwidth.map(r => r.serial)), calc.max(..high-bandwidth.map(r => r.serial))), suffix: "")，关键跳数的范围为 #value-range((calc.min(..high-bandwidth.map(r => r.hops)), calc.max(..high-bandwidth.map(r => r.hops))), suffix: "")。带宽提高八倍后，时延从 #number(high-bandwidth.first().mean_ns / 1e6, digits: 4) ms 降至 #number(high-bandwidth.last().mean_ns / 1e6, digits: 4) ms，主要来自每跳传输时间下降。这组单副本搜索的串行结构变化较小，后续多副本阶段继续为共激活专家增加可选执行位置。

== 复制预算驱动的两条搜索路径

上一节的结构分析已经揭示计算与通信的取舍，多副本由此获得新的驻留自由度。两种初始布局在相同总预算下独立推进，每轮入选部署作为各自下一轮的起点。

计算均衡起点降低节点热点，状态感知超图起点优化 Decode 结构。验证选择以三种 Prefill 规模在同预算下的最好值为参照，采用目标 2% 与最小可实现最大回退中的较大者作为有效门限，再从门限内选择 Decode 时延最低的部署。

=== 入选来源随预算变化

@fig:method-capacity-mainline 展示各预算入选部署的归一化速度与吞吐量。顶部色带记录 Planar 与 Vertical 在每档预算下的初始布局来源。

#figure(
  image("/assets/figures/method-capacity-mainline.pdf", width: 82%),
  caption: [Selected-Deployment Performance over Replica Budgets. Columns: 0.5/2/8 GB/s. Rows: normalized Decode speed and Prefill throughput at T32/T128/T512. Curves show Planar and Vertical; P/V tracks show the selected compute-balanced or hypergraph initial layout. The full-workload compute-balanced single-copy baseline is 1.],
) <fig:method-capacity-mainline>

#figure(
  table(
    fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
    columns: (0.75fr, 0.55fr, 3.0fr),
    align: (left, right, left),
    table.header([*配置*], [*带宽*], [*逐预算入选来源*]),
    ..result.curves.map(row => (
      [#profile-name(row.profile)], [#number(row.bandwidth)],
      [#row.runs.map(run => {
        let budget = if run.first == run.last { str(run.first) } else { str(run.first) + "–" + str(run.last) }
        budget + "% " + (if run.anchor == "compute-balanced" { "B" } else { "H" })
      }).join("；")],
    )).flatten(),
  ),
  caption: figure.caption(position: top, [当前批次的入选路径。B 为计算均衡，H 为超图，带宽单位为 GB/s。]),
) <tab:budget-selection-source>

低带宽的 Planar 与 Vertical 配置在全部 21 个预算点选择计算均衡路径；2/8 GB/s 配置的 20% 终点选择超图路径。中间预算仍会发生来源切换，具体区间见 @tab:budget-selection-source。每一轮新增副本投向、节点位置和位置交换都会进入下一轮，早期布局差异被逐档写进后续驻留组合。

=== 逐预算搜索的系统收益

@tab:envelope-20-percent 使用同配置的全工作量均衡单副本部署作为比较基线，报告 20% 入选部署的验证集收益。

#figure(
  table(
    fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
    columns: (0.82fr, 0.65fr, 0.83fr, 0.83fr, 0.83fr, 0.83fr),
    align: (left, right, right, right, right, right),
    table.header([*Profile*], [*GB/s*], [*Decode*], [*T32*], [*T128*], [*T512*]),
    ..result.curves.map(row => (
      [#profile-name(row.profile)], [#number(row.bandwidth)],
      [#number(performance-ratio(row.end.decode), digits: 3)],
      ..("32", "128", "512").map(t => [#number(performance-ratio(row.end.at(t)), digits: 3)]),
    )).flatten(),
  ),
  caption: figure.caption(position: top, [Normalized Decode Speed and Prefill Throughput at 20% Replication. The full-workload compute-balanced single-copy baseline is 1; bandwidth is in GB/s.]),
) <tab:envelope-20-percent>

20% 终点的 Decode 改善为 #value-range(result.ranges.validation.decode)，T512 改善为 #value-range(result.ranges.validation.at("512"))。T32 与 T128 分别改善 #value-range(result.ranges.validation.at("32")) 和 #value-range(result.ranges.validation.at("128"))。Decode 与 Prefill 的收益随硬件和窗口规模变化。

== 复制容量的双重物理作用

Prefill 同时推进大量 Token，副本增加热点专家可用的并发服务位置；Decode 每层只为当前 Token 执行一组活跃专家，副本增加的是专家绑定与规约路径的选择。*对 Prefill，副本首先改变负载能够流向哪里；对 Decode，副本持续改变关键路径能够怎样组成。*

=== Prefill 热点分流与容量饱和

一副本状态下，热点专家的全部请求只能进入唯一驻留位置，多个 Token 会在同一节点积累长队。复制这些专家后，请求可以分流到不同节点，窗口完成时间随最忙节点的工作量下降。@fig:method-capacity-prefill-mechanism 将代表性 T512 部署分成平均计算服务、节点峰均差、通信压力和执行残差；最后一项表示最繁忙资源工作量之外由依赖和调度产生的时间。

#figure(
  image("/assets/figures/method-capacity-prefill-mechanism.pdf", width: 100%),
  caption: [代表性 T512 配置的 Prefill 资源分解。前段副本压缩节点峰均差，执行残差由资源与依赖下界计算。],
) <fig:method-capacity-prefill-mechanism>

约 5% 预算已取得 T512 终点收益的 #value-range(result.ranges.five_percent_share.at("512"))。一个新增驻留位置会同时分流等待该专家的 Token，并把计算工作从峰值节点迁往空闲节点。随着高频专家获得足够的服务位置，最忙节点逐渐逼近全网平均工作量；继续复制只能修正次级热点，窗口内必须执行的专家计算总量保持不变。六组 20% 部署的执行残差比例为 #value-range(result.ranges.t512_execution_residual)。首个 1% 点的 T512 收益范围为 #value-range(result.ranges.one_percent_t512)，早期收益受计算与通信共同影响。

@fig:prefill-node-load-timeline 把同一结论展开到执行时间轴。Planar、2 GB/s 的 20% 部署在 T32、T128 和 T512 下分别达到 #pct(100 * result.timeline.at("32").compute_service_exposure, digits: 1)/#pct(100 * result.timeline.at("128").compute_service_exposure, digits: 1)/#pct(100 * result.timeline.at("512").compute_service_exposure, digits: 1) 的平均计算利用率；窗口增长主要延长中段持续计算区间，归一化空闲面积从 #pct(100 * result.timeline.at("32").idle_area, digits: 1) 缩到 #pct(100 * result.timeline.at("512").idle_area, digits: 1)。

#figure(
  image("/assets/figures/prefill-node-load-timeline.pdf", width: 100%),
  caption: [Planar、2 GB/s、20% 入选部署的代表性验证窗口时间线。T32/T128/T512 的完成时间为 #number(result.timeline.at("32").makespan_ns / 1e6, digits: 1)/#number(result.timeline.at("128").makespan_ns / 1e6, digits: 1)/#number(result.timeline.at("512").makespan_ns / 1e6, digits: 1) ms。],
) <fig:prefill-node-load-timeline>

T32 仍有明显的启动、依赖等待与排空空隙，副本和调度可以继续填补这些间断；T512 的聚合计算占用在主体区间接近满载，剩余空闲集中在首尾边界。窗口越长，这些固定边界被摊得越薄，性能越接近总计算工作量决定的服务时间。*复制消除热点分布后，模型必需计算成为 Prefill 的主要下界，容量收益随之快速收敛。*

=== Decode 驻留选择与结构重组

Decode 的出发点恰好相反。每个 Token 始终为每个活跃专家计算一次，复制保持专家计算工作量不变，同时增加专家的可选节点，并连带改变本层输出规约位置和下一层输入位置。@fig:method-capacity-decode-components 将入选部署的时延分为专家计算、节点串行、Mesh 服务和集合通信等待。专家计算在 0%–20% 内保持稳定，副本通过重组后面三项降低关键路径。

#figure(
  image("/assets/figures/method-capacity-decode-components.pdf", width: 100%),
  caption: [0%–20% 入选包络的 Decode 物理时延分解。低带宽主要减少 Mesh 服务，高带宽主要减少节点串行。],
) <fig:method-capacity-decode-components>

带宽决定新增位置主要改写哪一项。$0.5 " GB/s"$ 下，搜索把副本放到更接近输入和规约位置的节点，Mesh 服务总体下降；$8 " GB/s"$ 下，额外通信已经便宜，搜索更愿意把共激活专家分散到不同节点，节点串行总体下降；$2 " GB/s"$ 同时保留两种调整方向。每增加一批副本，专家绑定、规约位置和下一层起点都会产生新的组合，后续搜索面对持续扩张的离散路径空间。Prefill 的空间随峰值工作量逼近平均工作量而收缩，Decode 的空间则随驻留组合增加而扩张。

这也解释了 Decode 收益为何跨硬件显著分化。低带宽给短通信路径更高价值，高带宽给计算分散更高价值，Planar 与 Vertical 的本地服务时间又决定串行计算的耗时；同样的 20% 容量因此被组织成不同的关键路径。*Decode 的后段收益来自驻留组合持续增加，而收益方向由目标硬件决定。*

=== 双目标边际价值的分化

@fig:searched-capacity-curve 将逐预算入选部署的累计时延改善与复制预算放在同一坐标中。虚线表示归一化性能等于 1 加预算比例，实心点表示该档归一化性能的增量至少达到预算增量。Decode 曲线表示归一化速度，Prefill 曲线表示归一化吞吐量，均以同配置的全工作量均衡单副本基准为 1。

#figure(
  image("/assets/figures/searched-capacity-curve.pdf", width: 100%),
  supplement: [Figure],
  caption: [Normalized Speed and Throughput of Selected Deployments over 0%–20% Replica Budgets. The baseline is 1. Dashed lines show performance = 1 + replica-budget fraction. Filled markers identify performance increments reaching the budget increment.],
) <fig:searched-capacity-curve>

曲线把分化归结为两组清楚的边际收益。T512 在约 5% 预算取得终点收益的 #value-range(result.ranges.five_percent_share.at("512"))，10%–20% 再改善 #value-range(result.ranges.late.at("512"), suffix: "") 个百分点；Decode 在同一区间仍改善 #value-range(result.ranges.late.decode, suffix: "") 个百分点。T32 与 T128 位于两端之间：短窗口仍保留启动和排空空隙，10%–20% 分别继续改善 #value-range(result.ranges.late.at("32"), suffix: "") 和 #value-range(result.ranges.late.at("128"), suffix: "") 个百分点。

这组边际价值决定了交织顺序。Prefill 分配器先依据跨 Token 累积需求决定哪些专家需要新增服务位置，快速压低节点热点；Decode 搜索随后在这组副本上重排专家绑定和规约路径，并用 $epsilon_P=2\%$ 的门控保住已经形成的 Prefill 负载均衡。*前段预算主要修复并发服务容量，后段预算主要扩展 Decode 路径选择；交织优化让同一份副本依次承担这两种作用。*

== 在线调度消融

静态部署确定了可选物理节点集合，运行时仍需完成两项决策：本层输出汇聚位置，以及当前任务选用的具体副本。@fig:dataflow-linear-ablation 固定六份 20% 终点部署并在测试路由上逐步增强调度器所能利用的运行时信息。

#figure(
  image("/assets/figures/dataflow-linear-ablation.pdf", width: 100%),
  caption: [Scheduling Ablation on Frozen 20% Deployments. Decode uses normalized speed relative to nearest-replica binding with source-root reduction. Prefill uses normalized throughput relative to round-robin dispatch under the same reduction and fixed-tree rules. Each baseline is 1.],
) <fig:dataflow-linear-ablation>

#let flow-p-low = result.dataflow.find(r => r.profile == "planar" and r.bandwidth == 0.5)
#let flow-v-low = result.dataflow.find(r => r.profile == "vertical" and r.bandwidth == 0.5)
#let flow-p-high = result.dataflow.find(r => r.profile == "planar" and r.bandwidth == 8)
#let flow-v-high = result.dataflow.find(r => r.profile == "vertical" and r.bandwidth == 8)

在 0.5 GB/s 下，只开放动态规约根就使 Planar 和 Vertical 的 Decode 时延分别降低 #pct(flow-p-low.decode_root)/#pct(flow-v-low.decode_root)；继续联合选择副本与规约根，再增加 #number(flow-p-low.decode_joint - flow-p-low.decode_root)/#number(flow-v-low.decode_joint - flow-v-low.decode_root) 个百分点。到 8 GB/s 时，动态规约根单独贡献 #pct(flow-p-high.decode_root)/#pct(flow-v-high.decode_root)，联合规划将累计收益提高到 #pct(flow-p-high.decode_joint)/#pct(flow-v-high.decode_joint)。低带宽更依赖跨层规约位置，高带宽则更能利用多副本提供的计算位置。

Prefill 以轮转分派为 baseline，在同一部署上用累计工作量主线改善节点工作分布。DeepSeek-V3 六组配置的 T32/T128/T512 时延收益范围为 #value-range((calc.min(..result.dataflow.map(r => r.prefill.at("32"))), calc.max(..result.dataflow.map(r => r.prefill.at("32")))))、#value-range((calc.min(..result.dataflow.map(r => r.prefill.at("128"))), calc.max(..result.dataflow.map(r => r.prefill.at("128")))))、#value-range((calc.min(..result.dataflow.map(r => r.prefill.at("512"))), calc.max(..result.dataflow.map(r => r.prefill.at("512")))))，计算与通信队列继续显式推进。

== Operator Scope Extension

原有映射范围扩展实验比较 Dense + MoE 与 Dense + MoE + QKVO 两种方案，使用 Planar、0.5 GB/s、10% 额外副本及当时冻结的相同测试路由。@fig:qkvo-mapping-obstruction 保留这组实验，观察增加注意力投影权重后，常驻容量与必经计算工作如何共同改变性能。

#figure(
  image("/assets/figures/qkvo-planar-obstruction.pdf", width: 94%),
  supplement: [Figure],
  caption: [Historical Operator-Scope Extension on Planar at 0.5 GB/s and a 10% Replica Budget. Left: normalized Decode speed. Right: normalized Prefill throughput. The matched Dense + MoE control is 1. Both configurations use the original frozen deployments and evaluation.],
) <fig:qkvo-mapping-obstruction>

QKVO 投影使可用 MoE 驻留数量从 19,570 降至 19,284，减少 1.46%，并为每个 Token 增加 3.379 ms 的固定计算工作，相当于对照组的 50.51%。Decode 平均时延增至对照组的 2.78 倍，Prefill T512 完成时间从 246.12 ms 增至 427.49 ms。扩展映射范围同时改变存储占用与各层必需执行的计算，实验中固定计算工作的增加主导了完成时间的变化。
