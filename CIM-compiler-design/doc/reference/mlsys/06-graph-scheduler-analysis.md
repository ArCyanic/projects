# MLSys 2026 Graph Scheduler 搜索与仿真设计解析

## 0. 一句话结论

`mlsys-2026-graph-scheduler` 的优雅之处不是用了复杂 solver，而是把调度问题压成四个小而硬的层次：

```text
GraphInfo 只读事实索引
  -> CandidateGenerator 只枚举少量结构模板
  -> BeamSearchScheduler 搜索“覆盖度 + 慢存可见性 + 快存保留”状态
  -> Evaluator / TileSimulator 对每个候选做 tile-time legality + latency simulation
```

它用约 2.5k 行 C++ 源码实现了完整 pipeline，其中核心搜索/剪枝/仿真文件约千行级：

| 模块 | 文件 | 角色 |
| --- | --- | --- |
| 问题/输出模型 | `source/mlsys.h` | `Problem` / `Subgraph` / `Solution` 数据面 |
| 图事实索引 | `source/graph_utils.{h,cpp}` | producer/consumer/topo/boundary/external-input 查询 |
| 搜索状态 | `source/search_types.h` | `CandidateType` / `Candidate` / `SearchConfig` / `ScheduleState` |
| 候选生成 | `source/candidate_generator.{h,cpp}` | single op、linear chain、backward cone、recompute cone |
| Beam search | `source/state_search.{h,cpp}` | 状态展开、去重、beam 裁剪、终止 |
| 保留策略 | `source/retention_policy.{h,cpp}` | boundary output retain 集合枚举 |
| 代价评估 | `source/cost_model.{h,cpp}` | granularity / traversal / retention 组合选择 |
| Tile 仿真 | `source/tile_simulator.{h,cpp}` | working-set、split-k accumulator、load/store latency |

对我们最直接的帮助是：**把 CIM 调度也做成“瞬时 planning evidence + carrier materialization”的小搜索器，而不是建设长期 debug/provenance/sidecar 体系；生产事实仍必须 materialize 到 Flow、Stream/HAL、bufferization/memref、HAL-variant CIM target ops 和 typed object projection。**

---

## 1. 数据模型：搜索状态同时携带调度与内存可见性

### 1.1 目标项目的数据面

`source/mlsys.h` 把输入问题压得很薄：

- `Tensor { width, height }`；
- `Op { op_type, inputs, outputs, base_cost }`；
- `Problem { tensors, ops, fast_memory_capacity, slow_memory_bandwidth, native_granularity }`；
- `Subgraph { ops, tensors_to_retain, granularity, traversal_order, subgraph_latency }`；
- `Solution { subgraphs }`。

这个模型刻意没有复杂 IR。它只保留搜索必需事实：图、容量、带宽、native granularity、候选子图输出。对 CIM 的启示是：planner 内部可以有轻量 evidence 结构，但不要让它成为 executable IR；选中的事实必须回落到 owner carrier。

### 1.2 `ScheduleState` 是全局搜索 contract

`source/search_types.h:41-52` 的 `ScheduleState` 是整个搜索器最重要的结构：

```text
covered_ops       已经被当前 partial schedule 覆盖的 op
stored_tensors    已经写回 slow memory、后续可重新加载的 tensor
resident_tensors  只跨一个 boundary 留在 fast memory 的 tensor
covered_count     快速终止计数
total_latency     当前路径累计 latency
schedule          已接受的 subgraph 序列
```

这比“只搜索 op 顺序”强得多。它把“同样已调度了哪些 op，但边界后还能看见哪些 tensor”作为一等状态。对 CIM 来说，等价状态应至少区分：

| graph-scheduler 状态 | CIM 映射 |
| --- | --- |
| `covered_ops` | 已进入当前 dispatch/tile schedule 的 semantic op 或 tile-op |
| `stored_tensors` | 已有 owner-carried slow/DRAM/host-visible 副本的 tensor/tile region |
| `resident_tensors` | 当前 boundary 后仍在 SRAM 的 activation/output/partial-sum/bias tile region |
| `total_latency` | 由 cost terms 聚合出的规划代价，不能替代 runtime ABI |

关键借鉴：**CIM planner 不应只存“当前 SRAM 用了多少”，而要存“哪些值可见、可见到哪一个 boundary”。** 当前实现的阶段边界见 `doc/pipeline.md`。

---

## 2. 图事实索引：把复杂判断收束到 `GraphInfo`

`source/graph_utils.cpp` 先构建只读事实库，再让候选生成、评估和仿真共享它。

### 2.1 producer/consumer/topo 三件套

`GraphInfo::build_tensor_maps()` 做了四件事：

1. 建 `producer_of_tensor_`；
2. 建 `consumers_of_tensor_` / `tensor_usage_info_`；
3. 推导 `is_graph_input_` / `is_graph_output_`；
4. 拒绝 tensor 越界和多 producer。

`GraphInfo::build_op_adjacency()` 从 tensor producer 反推 op-level `pred_ops_` / `succ_ops_`。`GraphInfo::build_topo_order()` 用 Kahn topo sort 拒绝非 DAG。

这个分层让后续逻辑不用重复扫描图，也不用在多个模块里重新解释“边界输入/输出”。对 CIM 的直接建议：建立一个只读 planning fact view，集中提供：

- semantic op / dispatch / tile 的 producer-consumer；
- tensor/tile region 的 uses；
- graph input/output；
- topological order；
- boundary input/output 查询；
- matmul/linear/eltwise/reshape 等类别判断。

该 view 只能是 planning evidence；不能被 runtime 或 object loader 消费。

### 2.2 子图边界是候选合法性的核心

`GraphInfo::subset_boundary_outputs(ops)`：某个输出 tensor 只要是 graph output，或存在 candidate 外 consumer，就是 boundary output。

`GraphInfo::subset_external_inputs(ops)`：某个输入 tensor 的 producer 不在 candidate 内，或无 producer，就是 external input。

`GraphInfo::topo_sort_subset(ops)`：把 cone 中收集到的 op 重新按拓扑序排序。

这三个函数是 `CandidateGenerator`、`Evaluator`、`retention_policy` 的共同基础。对 CIM 来说，等价函数应服务两个问题：

1. 某个 fusion/tile candidate 需要从 SRAM/DRAM/常量区读哪些外部 tile？
2. candidate 执行后哪些 tile 必须对外可见或可被下一步立即消费？

---

## 3. 搜索空间构建：少量结构模板，而不是全子图枚举

### 3.1 候选类型是第一层剪枝

`source/search_types.h:9-15` 定义：

- `SingleOp`；
- `LinearChain`；
- `MatMulPointwiseChain`；
- `BackwardCone`；
- `RecomputeCone`。

`source/candidate_generator.cpp:15-37` 的 `CandidateGenerator::generate()` 只合并三类来源：

1. `generate_linear_candidates(state)`；
2. `generate_backward_cone_candidates(state, false)`；
3. `generate_backward_cone_candidates(state, true)`。

最后用短字符串 key 做候选去重。这个 key 只是内存中临时剪枝手段，不是 stable identity、hash、report 或 production contract；CIM 不应把类似 key 放入 object/runtime ABI。

### 3.2 Linear chain：只扩单入单出且输入已可用的窄链

`generate_linear_candidates()` 的流程：

1. 按 topological order 找未 covered 的 op；
2. 检查所有非 graph-input 输入都 `tensor_available(state, t)`；
3. 先生成 `SingleOp`；
4. 如果起点是 matmul，当前实现直接停止扩链；
5. 非 matmul 才继续沿唯一 successor 扩 `LinearChain`。

`is_linear_extendable()` 的关键限制：

- `next_op` 未 covered；
- `next_op` 不是 matmul；
- 当前 tail 只有一个 successor，且就是 `next_op`；
- `next_op` 只有一个 predecessor；
- `next_op` 的外部输入必须当前可用。

这使 linear chain 只覆盖低风险、局部收益明确的 pointwise-like 串。对 CIM 的启示：第一版不要做任意 DAG fusion。可先支持：

- single linear / matmul tile；
- linear + 紧邻 eltwise epilogue；
- 纯 eltwise chain；
- 小 backward cone。

### 3.3 Backward cone：从 pointwise tip 向上游闭包，matmul 硬排除

`expand_backward_cone()` 从 tip op 递归追输入 producer：

- 如果遇到 matmul，候选失败；
- 如果 `max_candidate_ops` budget 用尽，候选失败；
- producer 未 covered 时必须纳入 cone；
- producer 已 covered 时，只有在 `allow_recompute && depth < max_recompute_depth` 时才允许浅层重算；否则要求对应 tensor 已可用；
- 最终 candidate 必须大于 1 个 op，且 external inputs 可用。

这个设计非常值得借鉴：**重算不是一个全局模式，而是 cone 生成器的一条极小特例**。CIM 的 partial recompute 或 eltwise recompute 也应这么处理：只允许便宜、局部、深度受限的重算，不建设“兼容性恢复 lane”。

### 3.4 `MatMulPointwiseChain`：设计预留但当前未启用

`CandidateType` 和 `Evaluator` 都保留了 `MatMulPointwiseChain`，`TileSimulator` 也有 `is_matmul_pointwise_chain_candidate()` 支持。但 `candidate_generator.cpp:186-205` 中 matmul 后接 pointwise 的生成逻辑被注释掉。

因此它只能作为设计思路参考，不能当作目标项目已经充分验证的搜索入口。对 CIM 来说，linear/MatMul + eltwise epilogue 仍是高价值候选，但实现时应单独验证，不要直接相信这一路径已经在目标项目主线中闭环。

---

## 4. Beam search：状态展开、去重和剪枝都极硬

### 4.1 主循环结构

`BeamSearchScheduler::build_solution()` 在 `source/state_search.cpp:81-224`。流程：

```text
initial state:
  covered_ops = false
  stored_tensors = graph inputs
  resident_tensors = false

for step in max_search_steps:
  if any beam state complete: return best complete
  expanded_beam = []
  for state in beam:
    candidates = CandidateGenerator::generate(state)
    sort candidates by large ops first, non-recompute first, stable tip_op
    truncate to max_candidate_num
    for candidate in candidates:
      reject if it violates resident-consumption rule
      eval = Evaluator(state, candidate).evaluate_candidate()
      reject if eval fails
      apply subgraph -> next_state
      push next_state
  deduplicate expanded states by covered/stored/resident
  sort by estimated total latency, tie-break more covered ops
  truncate to beam_width
```

### 4.2 状态 key 不能只看 covered ops

`state_key()` 由三个位图组成：

```text
covered_ops | stored_tensors | resident_tensors
```

同一 covered set 下，哪些 tensor 已存慢存、哪些 tensor 只在 fast memory 暂住，会决定后续 candidate 是否可执行，也会改变搬运成本。CIM 搜索也必须这样区分：

- 同一 tile schedule 前缀，如果 partial-sum 留在 SRAM 与已经写回，是两个状态；
- 同一 dispatch 覆盖度，如果 bias/activation tile 常驻与否，是两个状态；
- 同一 op 覆盖度，如果 weight rectangle 已映射/已驻留，是两个状态。

### 4.3 Resident tensor 的强约束是关键剪枝

`consumes_required_residents()` 规则：如果 tensor 是 `resident=true` 且 `stored=false`，那么所有未 covered 的 consumer 都必须在当前 candidate 内；否则拒绝。

这条规则等价于：**fast-memory retain 只跨一个 boundary，不是长期 cache，也不会免费写回 slow memory。**

对 CIM 极有价值：

- SRAM 中的 activation tile 如果没写回，就必须被下一候选完全消费；
- partial-sum tile 如果跨 Cin chunk 保留，就只能服务明确的后续 reduction/epilogue；
- 不允许 planner 偷偷假设 runtime 会保留很久或自动 repair。

这与本仓库“生产代码不保留 defensive logic / runtime no repair”的策略一致。

### 4.4 搜索规模由配置硬上限控制

`SearchConfig` 默认：

- `beam_width = 8`；
- `max_candidate_ops = 6`；
- `max_chain_len = 16`；
- `max_recompute_depth = 2`；
- `max_retained_outputs = 2`；
- `max_search_steps = 512`；
- `max_candidate_num = 48`。

`Solver::solve()` 在大图上进一步降档：

- op 数 > 80：`beam_width=5`、`max_candidate_ops=5`、`max_recompute_depth=1`、`max_retained_outputs=1`；
- op 数 > 50：`beam_width=4`、`max_candidate_ops=5`。

关键不是“beam 越宽越好”，而是“先保证 bounded search”。这非常适合本仓库代码预算要求：宁可少量高价值搜索，也不要靠巨大 helper tree 和 fallback 维持复杂空间。

---

## 5. Retention policy：只保留马上能兑现的 boundary output

`source/retention_policy.cpp` 是全项目最值得抄思想的剪枝之一。

### 5.1 评分规则

`retention_score()` 对 boundary output 打分：

1. graph output 不 retain；
2. 统计未 covered consumer；
3. 只接受 `remaining_consumers == 1 && ready_consumers == 1`；
4. 分数为 `transfer_time(tensor_size) * 2 * immediacy`；
5. `immediacy = 1 / nearest_consumer_distance`。

它拒绝多消费者、远期消费者、不立即 ready 的 tensor。看起来保守，但它换来两个好处：

- 搜索空间小；
- resident tensor 的 one-boundary 语义容易保持真实。

### 5.2 枚举规则

`enumerate_retention_choices()`：

- 一定包含空 retain；
- tensor 元素数超过 fast memory capacity 时不考虑；
- 只取排名前 6 的 tensor；
- 枚举单 tensor retain；
- 如果 `max_retained_outputs >= 2`，再枚举 pair，且 pair 总大小不能超 capacity；
- 不枚举 3 个及以上 retain。

对 CIM 第一版建议直接采用同样保守原则：

| 保留对象 | 第一版规则 |
| --- | --- |
| output tile | 只有一个下游、下一步 ready、节省 copy 才 retain |
| partial-sum tile | 只在明确连续 Cin chunk / epilogue 消费时 retain |
| bias tile | 只在下一步 linear/eltwise 立即消费时 retain |
| activation tile | fanout 多时默认写回或重新加载，不做长期 cache 假设 |

后续可以扩展“短窗口多消费者”，但不要一开始就引入宽泛 cache policy。

---

## 6. Evaluator：结构候选必须通过 tile-time simulation 才能入 beam

### 6.1 先分类再枚举

`Evaluator::summarize_candidate()` 先计算：

- `boundary_outputs`；
- `external_inputs`；
- `tip_output_tensor`；
- 是否 linear；
- 是否 single matmul；
- 是否 matmul-pointwise chain；
- 是否包含 matmul；
- 是否全 pointwise。

`Evaluator::evaluate_candidate()` 再按类型选择评估路径：

- single matmul：`evaluate_single_matmul_candidate()`；
- matmul-pointwise chain：复用 single matmul 路径；
- all pointwise：`evaluate_pointwise_candidate()`；
- 其他：枚举 `(w, h, k)`。

这给 CIM 一个清晰分层：候选结构本身不直接给 cost；必须先转成 tile granularity、traversal、retention，再由 simulator 判合法。

### 6.2 Granularity 搜索：从大到小的稀疏离散序列

`make_dim_choices(dim, native_dim)` 从 `min(dim, native_dim)` 开始不断除以 2，直到 1。`make_spatial_choices()` 按面积降序排列 `(w,h)`。`make_k_choices()` 对 matmul 的 reduction 维也从最大可行值开始按 2 衰减。

这种枚举不是完备搜索，而是硬编码了一个高价值偏序：**先试大 tile，大 tile 不合法才退到小 tile。**

对 CIM 的直接映射：

```text
B/Cout/Cin tile candidates:
  从 profile/native tile 上限开始
  按硬件友好的二分/整除序列下降
  先试 SRAM 压力小且阵列利用率高的主线组合
  simulator 判非法就缩小，不做 repair
```

### 6.3 提前停止：同面积找到可行解后不继续看更小面积

`evaluate_pointwise_candidate()` 和 `evaluate_single_matmul_candidate()` 都有 early return：当遍历到更小 area 时，如果当前 area 已经找到可行最优，就直接返回。

这是极有用的比赛策略：大 tile 通常减少边界和搬运；如果已经可行，继续试更碎 tile 的收益低但成本高。CIM 的 tile search 也可以类似：

- 对同一主导容量层级，找 best；
- 如果该层级可行，停止向更碎 tile 下降；
- 只有 OOM 或 owner-carrier 约束失败时才缩 tile。

### 6.4 Traversal order：matmul 用 snake，其余 raster

`evaluate_at_granularity()` 对 `has_matmul` 的候选使用 snake traversal，否则使用 raster traversal。

`build_snake_order()` 按行交替正反方向遍历 tile，目的是复用相邻 tile 的输入 footprint。CIM 不应原样绑定到 2D snake，但应保留这个抽象：

```text
traversal_order candidate family:
  raster
  snake
  Cout-major
  Cin-major
  array-shape-major
```

选择 traversal 后再交给 simulator 判 SRAM / array / copy cost，而不是写死在 runtime。

---

## 7. TileSimulator：目标项目最核心的“合法性即仿真”思想

`source/tile_simulator.cpp` 的 `TileSimulator::simulate()` 是整个项目的质量核心。它不是公式估分，而是 tile-by-tile 检查 working set。

### 7.1 主流程

对每个 spatial tile 和每个 split-k step：

1. `build_step_requirements(tile_row, tile_col, k_begin)` 递归收集本 step 的：
   - external input rects；
   - boundary output rects；
   - accumulator rects；
   - compute latency；
2. 计算 `additional_load`；
3. 合成 `step_footprint`：fixed resident + retained boundary + external inputs + boundary outputs + accumulators；
4. `union_area(step_footprint)` 得出 peak working set；
5. 超 `fast_memory_capacity` 则返回 `nullopt`，候选非法；
6. 计算 `additional_store`；
7. `latency += max(compute_latency, mem_latency)`；
8. 更新 `dynamic_cache = step.external_inputs`，只给下一 step 局部复用。

关键点：**OOM 判定和 latency 估计走同一个 simulator；不会出现 cost 看起来好但容量非法的候选进入 beam。**

### 7.2 矩形区域，不是整 tensor

`Rect` / `Range` / `StepRequirements` 让 simulator 追踪 tile 区域：

- `make_tensor_rect()` 根据 tile row/col 产生输出区域；
- `make_lhs_rect()` / `make_rhs_rect()` 从 output rect + k range 推导 matmul 输入区域；
- `collect_tensor_requirements()` 从输出需求递归追到 external inputs；
- `union_area()` 算矩形并集，避免重复计数；
- `incremental_area()` 只算新增 load/store 面积。

对 CIM 的直接价值：我们的 SRAM/weight/partial-sum 规划天然是 tile/rect/range 问题，不应只用 tensor-level size。建议 mapping：

| TileSimulator 概念 | CIM planner 概念 |
| --- | --- |
| `Rect` | activation/output/partial-sum SRAM tile rectangle |
| `Range` | Cin / reduction chunk / bit-serial depth range |
| `external_inputs` | 本 step 需从 DRAM/constant/previous carrier 读入的 tile |
| `boundary_outputs` | 本 step 完成后对外可见或需写回的 tile |
| `accumulators` | 跨 reduction chunk 存活的 partial-sum tile |
| `union_area` | SRAM live bytes / bank occupancy / weight rectangle live bits |
| `incremental_area` | 新增 copy bytes / weight load bits |

### 7.3 Split-k accumulator 是 partial-sum 生命周期的模板

`is_split_k_accumulator()` 判断：如果 tensor 由 candidate 内 matmul 生产，且当前 `reduction_range.size < full inner dim`，则它是 accumulator，需要计入 fast memory。

这与 CIM 的 `Cin` tile 累加完全同构：

```text
full inner dim         -> 完整 Cin
reduction_range        -> 当前 Cin tile
split-k accumulator    -> partial-sum tile
boundary_ready         -> 最后一个 Cin tile 完成，output 才可对外可见
```

CIM planner 应把 partial-sum tile 当成一等资源：

- 占 SRAM；
- 可跨连续 reduction step resident；
- 最后一个 chunk 后才成为 boundary output；
- 参与 sync / array interval / cost terms；
- 最终必须 materialize 到 HAL-variant CIM target carriers，不进入 runtime repair。

### 7.4 Latency 公式足够小，但抓住了主矛盾

`TileSimulator::simulate()` 用：

```text
mem_latency = transfer_time(additional_load + additional_store)
step_latency = max(compute_latency, mem_latency)
```

这是假设计算和搬运能重叠。对 CIM 可先借鉴这个“小公式、大约束”的思路：

- 第一版 cost 可以保守简单；
- 但 legality 必须严格；
- simulator 输出直接映射到 `CIMCostTerms` 类似字段，如 `memCopyBytes`、`sramPeakLiveBytes`、`arrayLoadImbalance`、`partialSumCrossArrayCount`；
- 不要为了 cost 精细化引入 debug traces、sidecar replay 或 runtime fallback。

---

## 8. 对 CIM-compiler-design 的直接落点

### 8.1 先做 transient planning service，不做新 runtime contract

本仓库当前 active rule 已明确：scheduler 是 constraint solver 和 evidence producer，不拥有 runtime facts。借鉴目标项目时也必须保持：

```text
Captured CIM problem/profile facts
  -> transient search state / candidate / simulator evidence
  -> selected intents
  -> materialize into Flow / Stream-HAL / bufferization-memref / HAL-variant CIM target ops
  -> typed object projection
  -> runtime consumes verified carrier facts only
```

不要新增：

- planner JSON sidecar；
- score matrix；
- stable candidate id；
- replay/provenance/debug schema；
- runtime loader repair 或 fallback；
- Python post-semantic lowering state。

### 8.2 最小可落地设计

建议把可借鉴机制拆成 5 个 pass-local 小职责，全部作为 transient planning evidence：

| 职责 | 内容 | 目标项目来源 |
| --- | --- | --- |
| planning graph view | producer/consumer/topo/boundary 查询 | `GraphInfo` |
| schedule state | covered/stored/resident + cost | `ScheduleState` |
| candidate generation | single/tile-chain/cone/recompute 小模板 | `CandidateGenerator` |
| tile evaluation | granularity/traversal/retention 组合枚举 | `Evaluator` |
| tile simulation | working-set legality + cost terms | `TileSimulator` |

### 8.3 候选模板优先级

第一版只建议支持最直接收益的结构：

1. single linear/matmul tile；
2. linear/matmul + 紧邻 eltwise epilogue；
3. pure eltwise chain；
4. pure eltwise backward cone；
5. cheap eltwise recompute cone，深度 1 或 2。

暂不建议：

- 任意 DAG fusion；
- 多 consumer 长期 retain；
- runtime 动态选择 tile；
- 多 profile 分叉 planner；
- 以 debug dump 驱动 materialization。

### 8.4 Retention 第一版规则

直接采用保守策略：

```text
retain(tile) only if:
  tile is not final graph output needing slow visibility now
  tile fits SRAM
  remaining consumers == 1
  that consumer is ready in next candidate
  estimated saved copy cost > 0
  retained set size <= 1 or 2
```

这条规则牺牲一部分最优性，但换来：

- 搜索空间小；
- SRAM 生命周期真实；
- 不需要 repair；
- verifier 更容易写成 hard reject。

### 8.5 Simulator 输出到现有 cost terms

本仓库已有 `compiler_plugins/cim/src/cim/Transforms/CIMCostModel.h`，其中包含 `memCopyBytes`、`sramPeakLiveBytes`、`arrayLoadImbalance`、`partialSumCrossArrayCount` 等字段。Tile simulator 的输出可以直接投影到这些 planning/cost terms：

| Simulator evidence | `CIMCostTerms` 类输出 |
| --- | --- |
| `additional_load + additional_store` | `memCopyBytes` |
| `peak working set` | `sramPeakLiveBytes` |
| split-Cin accumulator live step | `partialSumCrossArrayCount` 或 partial-sum 相关项 |
| traversal / array occupancy imbalance | `arrayLoadImbalance` |
| rect union waste / bank waste | fragmentation 类项 |

注意：这些 cost terms 是编译期选择依据或 carrier materialization 辅助，不是 runtime 重新推理入口。

---

## 9. 不应原样照搬的点

1. **`estimated_total_latency()` 太粗**
   目标项目只用未 covered op 的 `0.10 * base_cost` 估剩余代价。CIM 的剩余代价必须至少考虑 SRAM pressure、copy bytes、partial-sum 生命周期、array occupancy/sync，否则 beam 排序会误导。

2. **`MatMulPointwiseChain` 当前未实际生成**
   虽然 evaluator/simulator 支持，但 generator 主线注释掉了 matmul 后接 pointwise 链。CIM 可以实现 linear+epilogue，但必须自己闭环验证。

3. **MatMul layout fallback 不适合作为 CIM 主线**
   `GraphInfo::get_inner_dim()` 和 `TileSimulator::detect_matmul_layout()` 对 swapped layout 有宽松分支。CIM 生产代码应依赖 semantic/captured carrier 的明确 layout，不做猜测式 fallback。

4. **目标项目的输出 JSON 不是我们的 ABI 参考**
   其 `Solution` JSON 很适合比赛提交，但本仓库必须把 selected facts materialize 到 MLIR/IREE owner carriers 和 typed object projection，不能新增 planner-output-as-runtime-input。

5. **Retention 可后续放宽，但不要第一版放宽**
   多消费者短窗口 retain 可能有收益，但会显著扩大状态空间。先用单消费者立即消费策略，等主线正确后再评估。

---

## 10. 推荐落地顺序

1. **只读建模**：实现/整理 pass-local planning fact view，集中 boundary/external-input/topo 查询。
2. **状态定义**：引入 transient `covered/stored/resident` 状态，不进入 ABI。
3. **候选模板**：先 single tile、eltwise chain、linear+epilogue、小 cone。
4. **tile simulator**：先做 strict legality：SRAM working set、partial-sum live、copy bytes。
5. **beam search**：beam/candidate/step 都硬上限，状态按 covered/stored/resident 去重。
6. **carrier materialization**：只把最终选中的 dispatch/resource/memory/placement facts 写入 owner carriers。
7. **verifier gate**：TargetBackend/runtime 只接受 carrier-backed facts，拒绝 planner evidence、dump、sidecar、debug/replay。

最重要的原则：**把搜索器写小，把 simulator 写真，把 materialization 写硬。** 目标项目的高效来自这个组合，而不是来自复杂框架。
