#import "../results.typ": result, number, pct, value-range, profile-name, performance-ratio

本附录给出当前 20% 预算终点的测试结果与公开／合成路由对照，数据来自统一全工作量初始化批次。

== 独立路由测试

六组 DeepSeek-V3 20% 入选部署在 4,096 条测试 Decode 路由与每种规模八个 Prefill 窗口上执行。@tab:frozen-test-results 报告测试集相对于验证集的平均时延变化，负值表示测试集时延更低。

#figure(
  table(
    fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
    columns: (0.78fr, 0.58fr, 1.0fr, 0.94fr, 1.35fr),
    align: (left, right, right, right, right),
    table.header([*计算配置*], [*带宽*], [*Decode 平均*], [*Decode P95*], [*Prefill 三规模范围*]),
    ..result.tests.map(row => (
      [#profile-name(row.profile)], [#number(row.bandwidth)],
      [#pct(row.decode)], [#pct(row.p95)], [#value-range(row.prefill_range)],
    )).flatten(),
  ),
  caption: figure.caption(position: top, [20% 终点从验证集到测试集的时延变化。Prefill 一列给出 T32、T128 和 T512 的变化范围，带宽单位为 GB/s。]),
) <tab:frozen-test-results>

六组配置的 Decode 平均时延最大绝对变化为 #pct(result.ranges.test_decode_abs)，P95 为 #pct(result.ranges.test_p95_abs)；Prefill 变化范围为 #value-range(result.ranges.test_prefill)。Decode 使用完整路由区间，Prefill 使用八个测试窗口与一个验证窗口进行比较。

== 公开与合成路由对照

DeepSeek-V2-Lite 与 Qwen2 分别使用公开路由和 seed0 合成路由运行相同配置，并相对各自路由来源的全工作量均衡单副本基线计算收益。配置为 Planar／Vertical、2 GB/s 和约 20% 额外副本。

#let source-data = json("/artifacts/results/cross-model-20pct.json").source_comparison
#figure(
  {
    set text(size: 8.5pt)
    table(
      fill: (_, y) => if y == 0 { rgb("#DCEAF7") } else { none },
      columns: (1.55fr, 0.7fr, 0.7fr, 0.7fr, 0.7fr, 0.7fr, 0.7fr),
      align: (left, left, left, right, right, right, right),
      table.header([*Model*], [*Profile*], [*Source*], [*Decode*], [*T32*], [*T128*], [*T512*]),
      ..source-data.pairs().map(((model, profiles)) => {
        ("planar", "vertical").map(profile => {
          ("public", "synthetic").map(source => {
            let gains = profiles.at(profile).at(source).gains
            (
              [#(if model == "deepseek-v2-lite" { "DSV2-Lite" } else { "Qwen2" })],
              [#profile-name(profile)], [#(if source == "public" { "Public" } else { "Synthetic" })],
              [#number(performance-ratio(gains.decode), digits: 3)], ..("32", "128", "512").map(t => [#number(performance-ratio(gains.prefill.at(t)), digits: 3)]),
            )
          }).flatten()
        }).flatten()
      }).flatten(),
    )
  },
  caption: figure.caption(position: top, [Normalized Decode Speed and Prefill Throughput under Public and Synthetic Routes. Each source uses its own full-workload compute-balanced baseline (1).]),
) <tab:source-comparison>

公开与合成路由均取得 Decode 与 Prefill 收益，具体幅度随模型、窗口规模和计算配置变化。DeepSeek-V2-Lite 的 T512 公开／合成收益较接近，Qwen2 的合成路由在较长窗口中取得更高收益。
