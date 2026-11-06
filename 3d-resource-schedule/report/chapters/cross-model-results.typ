#import "../results.typ": result, number, pct, value-range, profile-name

== 三模型总体结果 <sec:cross-model-results>

专家规模、共享专家数量和每次激活的专家数共同改变节点热点与关键路径。总体实验选择 DeepSeek-V3、DeepSeek-V2-Lite 和 Qwen2-57B-A14B，在相同的相对副本预算下评价同一套逐预算交替优化流程。Qwen2 与 DeepSeek-V2-Lite 使用公开路由数据，DeepSeek-V3 使用 seed0 主题相关合成路由，固定 $2 " GB/s"$ Mesh 带宽，并分别运行 Planar 与 Vertical。

#let cross-model-data = json("/artifacts/results/cross-model-20pct.json")

#figure(
  {
    set text(size: 9pt)
    table(
      columns: (1.7fr, 1fr, 1.15fr, 0.6fr, 0.75fr, 0.8fr, 0.9fr),
      align: (left, center, center, center, center, right, right),
      table.header(
        table.cell(fill: rgb("#DCEAF7"))[*模型*],
        table.cell(fill: rgb("#DCEAF7"))[*稠密/MoE 层*],
        table.cell(fill: rgb("#DCEAF7"))[*路由/共享标准块*],
        table.cell(fill: rgb("#DCEAF7"))[*Top-k*],
        table.cell(fill: rgb("#DCEAF7"))[*节点深度*],
        table.cell(fill: rgb("#DCEAF7"))[*新增副本*],
        table.cell(fill: rgb("#DCEAF7"))[*实际预算*],
      ),
      ..cross-model-data.models.map(model => {
        let spec = model.specification
        let entry = model.profiles.planar
        (
          [#model.name],
          [#spec.dense_layers/#(spec.model_layers - spec.dense_layers)],
          [#spec.routed_experts/#spec.shared_experts],
          [#spec.top_k],
          [#entry.node_geometry.at(2)],
          [#entry.extra_replicas],
          [#(str(calc.round(entry.realized_extra_replica_percent, digits: 3)) + "%")],
        )
      }).flatten(),
    )
  },
  caption: figure.caption(position: top, [三模型总体实验配置。路由专家数与共享 FFN 标准块数按每个 MoE 层计；Qwen2 的宽共享 FFN 展开为 8 个标准块。副本预算按完整 MoE 驻留数取整；两种计算配置使用相同的模型相对预算。]),
) <tab:cross-model-specifications>

三种模型共享 $4 times 4$ Mesh 和 1.5 倍模型权重容量规则；节点二维平面固定为 $8192 times 16384$，深度随模型体积缩放。@tab:cross-model-specifications 给出约 20% 预算对应的完整专家副本数。两条轨迹均从零复制推进至该预算，每轮使用相同的副本分配、固定副本数位置交换和 Prefill 门控。

基础映射、复制统计与精炼使用 4,096 条训练路由，其中超图拟合读取前 1,024 条。验证集使用 4,096 条 Decode 路由及每种 Prefill 规模的一个窗口选择部署。最终冻结全工作量均衡单副本基准和约 20% 入选部署，在 4,096 条测试路由及每种规模的 8 个独立 Prefill 窗口上重放；归一化速度与吞吐量均以各模型、各计算配置的计算均衡基准为 1。

#figure(
  image("/paper/figures/07-cross-model-results.pdf", width: 100%),
  supplement: [Figure],
  caption: [Cross-Model Normalized Decode Speed and Prefill Throughput at 2 GB/s and Approximately 20% Replication. Each model/profile uses its full-workload compute-balanced single-copy baseline (1). Test evaluation uses 4,096 Decode routes and eight windows per Prefill size.],
) <fig:report-cross-model-20pct>

@fig:report-cross-model-20pct 中，六组配置的 Decode 时延降低 #value-range(result.ranges.cross_decode)，Prefill 窗口完成时间降低 #value-range(result.ranges.cross_prefill)。DeepSeek-V3 的 Decode 改善为 #pct(result.cross_models.at(0).profiles.planar.decode)/#pct(result.cross_models.at(0).profiles.vertical.decode)，DeepSeek-V2-Lite 为 #pct(result.cross_models.at(1).profiles.planar.decode)/#pct(result.cross_models.at(1).profiles.vertical.decode)，Qwen2-57B-A14B 为 #pct(result.cross_models.at(2).profiles.planar.decode)/#pct(result.cross_models.at(2).profiles.vertical.decode)，各组数字依次对应 Planar/Vertical。三模型在有限副本预算下都取得了单请求关键路径与多请求并发服务的收益。

入选起点随模型和硬件变化：DeepSeek-V2-Lite 两种配置选择计算均衡路径，DeepSeek-V3 与 Qwen2 两种配置选择超图路径。逐预算比较两条完整路径，使不同模型的负载均衡需求和 Decode 结构收益共同参与部署选择。
