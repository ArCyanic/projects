# MLSys 2026 第三名 Rust/BLP Graph Scheduling 方案解析

## 0. 一句话结论

第三名项目走的是一条比前两份更“优化建模”的路线：

```text
ComputationGraph
  -> enumerate connected convex subgraphs
  -> per-subgraph tile search + latency benchmark
  -> BLP 选择执行 kernel set，允许 recomputation
  -> 对每个选中 subgraph 做 retention partition beam search
  -> snake traversal + JSON output
```

它不像 first-place 项目那样以 beam `ScheduleState` 为主，也不像 VNRC submission 那样以
FM/evolution 搜索 `Partition` / `CoupledPartition`。它把“选哪些 fused kernels 执行”转化成
Binary Linear Programming，由 `good_lp` + HiGHS 求解；再把 retention 当成已选 subgraph 内部的
二级 partition 问题。

对 CIM-compiler-design 最有价值的是：

1. **convex subgraph** 作为可融合 kernel 的严格结构约束；
2. **BLP selection** 原生表达 recomputation 与覆盖约束；
3. **tile propagation + exact-ish latency model** 把切片、adjacent reuse、split-k 统一到 cost；
4. **retention partition** 将“一步可见的 retained tensor”转化为子图切分，而不是全局长期 residency。

## 1. 资料入口与源码地图

主要文件：

- `README.md`：只说明这是 MLSys 2026 Graph Scheduling Competition submission。
- `writeup/main.tex`：最权威的算法叙述，明确来源是 Korch 的 BLP kernel selection 与 Welder 的 GraphConnecting。
- `Cargo.toml`：Rust 2024，依赖 `good_lp`、`highs`、`rayon`、`fraction`、`bitvec`、`serde_json`。
- `src/main.rs`：端到端 pipeline：读 JSON、抽 convex subgraphs、并行 benchmark、BLP selection、retention partition、输出 JSON。
- `src/graph.rs`：`ComputationGraph`、`Subgraph`、`Partition`、topological order、subgraph set algebra。
- `src/global_optimization.rs`：convex subgraph enumeration 与 BLP selection。
- `src/tiling.rs`：tile-shape propagation、working-set gate、traffic objective、retained reservation。
- `src/performance_model.rs`：roofline latency、slice names、adjacent implicit reuse、split-k compute scaling。
- `src/partition.rs`：selected subgraph 内部的 retained-edge beam search。
- `src/naive_scheduler.rs`：逐 op baseline。
- `src/output_format.rs`：输出 schema。

`CLAUDE.md` 有一段“main.rs 还只是 smoke test”的描述，但当前 `src/main.rs` 已经串起了完整 pipeline；
因此本文以源码与 writeup 为准，把 `CLAUDE.md` 当作设计笔记而非当前状态权威。

## 2. 顶层 pipeline

`src/main.rs` 的 `main()` 是当前端到端主线：

1. 解析输入 JSON 为 `InputFormat`；
2. 构造 `ComputationGraph`；
3. `extract_convex_subgraphs(&graph)` 枚举候选；
4. 对每个候选并行执行：
   - `search_tile_values(&subgraph, &device, &[])`；
   - `subgraph_latency(...)`；
   - `total_latency(...)`；
5. `optimize_execution_plan(&graph, &subgraph_costs)` 用 BLP 选择 subgraphs；
6. 对每个选中 subgraph 调 `search_partition` 搜 retained partition；
7. `topological_sort_subgraphs` 做 subgraph-level Kahn ordering；
8. `write_output` 写出 schedule JSON；
9. 可选 `--compare-naive` 输出 naive latency 与 speedup。

这条 pipeline 的明显特点是：

- 全局结构选择交给 BLP；
- tile/cost benchmark 在 BLP 前完成；
- retention 不参与 BLP，而是对选中 subgraph 做后续 partition；
- traversal 简化为 snake；
- 并行主要用于候选 benchmark 与 selected subgraph partition。

## 3. Graph 与 Subgraph 模型

### 3.1 `ComputationGraph`

`src/graph.rs` 的 `ComputationGraph::new` 从输入构造：

- `operations`；
- `tensors`；
- op inputs / outputs；
- tensor producer；
- tensor consumers；
- cached topological order。

它在构造时断言：

- widths/heights 长度一致；
- inputs/outputs/base_costs/op_types 与 op 数一致；
- tensor id 不越界；
- tensor 不允许多 producer。

这是一种较直接的 contest input trust + assert 风格。对 CIM production 来说，类似检查应该成为 public contract verifier，不能靠后续 fallback 修补。

### 3.2 `TopologicalOrder`

`ComputationGraph::topological_sort` 使用 `OnceLock` 缓存拓扑顺序，并维护 `position`。`Subgraph` 中的节点始终按 topo position 排序，`contains`、`is_subset`、`subtract`、`insert` 都利用这个不变量。

这对搜索很重要：大量子图集合操作可以保持稳定顺序，便于 hash、比较与输出。

### 3.3 `Subgraph`

第三名项目里的 `Subgraph<'a>` 比 VNRC 的 `Subgraph` 轻很多。它主要是：

- parent graph 引用；
- topo-sorted nodes；
- set algebra；
- `input_tensor_ids()`；
- `output_tensor_ids()`；
- `components()`。

它不直接携带 tile 约束、ephemeral 分类或 cost cache。执行语义分散在 `tiling.rs` 与
`performance_model.rs` 中。

这与 VNRC 的区别很大：VNRC 把 boundary / ephemeral / tile / cost 聚进一个 execution-subgraph object；
第三名方案保持 `Subgraph` 轻量，把优化建模放在全局 BLP 与独立 cost 函数里。

## 4. Convex subgraph enumeration

### 4.1 Convexity 定义

`writeup/main.tex` 引用 Korch 的定义：在 DAG 中，如果一个路径的两个端点都在子图里，那么路径上的
中间节点也必须在子图里，这个子图就是 convex。它保证 fused kernel 不会把内部传递依赖切到边界外。

这比“connected subgraph”更强：connected 只关心无向连通，convex 关心 DAG 路径闭包。

### 4.2 seed-and-grow 实现

`src/global_optimization.rs::extract_convex_subgraphs` 当前使用 seed-and-grow：

- 先按 topo order 建立 op position；
- 构造 pred/succ position 表；
- 预计算每个位置的 ancestor bitset 与 descendant bitset；
- 每个 op 作为 seed；
- 从当前集合的 pred/succ frontier 增长；
- 用 `anc(S') ∩ desc(S') ⊆ S'` 检查 convexity；
- 用 bitset hash 去重；
- `MAX_FUSION_SIZE = 7` 限制候选大小。

核心剪枝是 convexity bitset 检查和最大 fusion size。它没有枚举所有 output subset，也没有在全图上无限扩张。

### 4.3 对 CIM 的意义

Convexity 是一个非常适合 compiler planner 的结构约束：

- 保证 fused execution-subgraph 不切断内部传递依赖；
- 让子图边界更容易投影成 dispatch boundary；
- 防止 planner 产生“看似有收益但无法合法 lower”的非闭合 fusion；
- 可与 memory/resource constraints 叠加，而不替代它们。

CIM 第一版候选生成可以把 connected-convex 作为强默认，只在明确支持 recomputation 或 multi-carrier
OR-semantics 后再放宽。

## 5. BLP subgraph selection

### 5.1 问题建模

`src/global_optimization.rs::optimize_execution_plan` 为每个 benchmarked subgraph 建一个 binary variable `u_i`，
目标函数是：

```text
minimize Σ cost_i * u_i
```

约束分两类：

1. producer dependency constraint：如果某个 selected subgraph 消费 tensor `t`，那么至少要选择一个把 `t`
   的 producer op 作为 output producer 的 subgraph；
2. graph output coverage：每个产生 graph output 的 op 至少被某个 selected subgraph 覆盖。

这不是传统“每个 op 恰好一次”的 partition ILP。由于约束允许多个 subgraph 覆盖同一个 op，它天然支持
recomputation。

### 5.2 HiGHS 与时间限制

`Cargo.toml` 通过 `good_lp` 使用 HiGHS，并关闭 default features 以便静态链接。`optimize_execution_plan`
调用 `.set_time_limit(10.0)`，说明 LP 求解器被当成竞赛内的 bounded optimizer，而不是无限精确 oracle。

对 CIM 的启发：MILP/BLP 可作为 planning backend，但必须有明确预算和 fallback-free rejection 语义。若 solver
不能返回满足 verifier 的解，production pipeline 应拒绝或使用明确的较小搜索策略，而不是猜测填补。

### 5.3 与前两份方案的差别

- first-place：用 beam state 枚举 schedule，显式保留 resident tensors；
- VNRC：用 FM/evolution 搜 partition/coupling；
- 第三名：用 BLP 一次性选择 kernel set，再做 local retention partition。

第三名方案把“全局组合选择”交给数学优化器，所以代码量小于 VNRC，但表达 retention/context 的能力也更弱。

## 6. Tile search

### 6.1 `search_tile_values`

`src/tiling.rs::search_tile_values` 搜 `(w, h, k)`：

- spatial candidates 必须是所有 boundary outputs 宽/高的 common divisors；
- native granularity 限制 `w / h`，`native_k = min(native_w, native_h)`；
- `k` 必须整除每个 matmul 的 K；
- retained tensors 会先占用 fast memory capacity；
- `mixed_fusion_valid` 过滤 mixed MM/PW 几何不合法情况；
- `peak_working_set` 过滤容量不满足情况；
- `memory_traffic` 作为 ranking objective；
- tie-break 偏好更大的 `(w, h, k)`。

这是一条清晰的 legality → capacity → traffic objective 流程。

### 6.2 Tile-shape propagation

`propagate_op_dims` 从 subgraph output 反向推导每个 op 的迭代 tile：

- boundary output producer 直接使用全局 `(h, w, k)`；
- pointwise consumer 继承空间 shape；
- matmul consumer 的 LHS/RHS 分别映射到 `(m, k)` / `(k, n)`；
- inner matmul 使用完整 reduction，不独立 split。

这与 Welder 的 tile propagation 思想相近：不同 op 的局部 tile shape 不是独立枚举，而是从 output tile 反推。

### 6.3 Working set 与 retained reservation

`search_tile_values` 先把 retained tensor 全尺寸从 fast memory 容量中扣掉，再检查候选 subgraph 的
`peak_working_set`。这意味着 retention 会直接影响 tile choice。

与 VNRC 的 context-sensitive cost cache 类似，第三名方案也承认同一 subgraph 在不同 retained context 下
最优 tile 可能不同，只是没有建立全局 cache。

## 7. Performance model

### 7.1 Roofline metric

`src/performance_model.rs` 的 `PerformanceMetric` 有 compute cost 与 memory cost，`latency()` 取二者最大值。
这就是题目 roofline cost 的核心。

内部使用 `Fraction` 做精确算术，直到输出或 LP cost 才转 `f64`。这对竞赛例子的精确数值很重要。

### 7.2 Slice names 与 adjacent implicit reuse

`slice_names_for_output` 为一个 tile iteration 反向走 subgraph，生成需要 resident 的 slice names：

- `LhsRowStrip`；
- `RhsColStrip`；
- `OutAccumulator`；
- `PointwiseTile`。

`ResidencySet` 只跟踪上一 iteration 的 resident slice，且 `Whole(T)` 可以覆盖 partial access。`subgraph_latency`
在每个 iteration 后用 `cached_inputs.replace(...)` 更新缓存，因此隐式 reuse 是 adjacent-only。

这比简单按 tensor 全量 load/store 精确得多，尤其能表达 raster/snake 相邻 tile 复用和 partial-slice 复用限制。

### 7.3 Split-k compute scaling 与 output eviction

`subgraph_latency` 根据 output producer 的 reduction size 计算 `reduction_counts`，每个 k step 的 compute 按
实际 `reduction_tile_size / reduction_size` 缩放。output eviction 只在 spatial tile 的最后 k step 计费。

这与前两份项目共同强调的一点一致：split-k accumulator 生命周期是硬件 planning 的核心，不能只把 k-split
当成普通循环展开。

### 7.4 Traversal order

`writeup/main.tex` 说 solver 总是使用 snake traversal，因为竞赛设定里 implicit reuse 只发生在相邻 step。
`src/main.rs::snake_traversal` 也按 output tile grid 生成 snake order；若行/列少于 2，则输出 `null`。

相比 first-place 项目按 candidate 类型决定 traversal，第三名方案更激进地固定 snake。这简化输出，但对更复杂
CIM dataflow 未必足够。

## 8. Retention partition

### 8.1 Retention 被转化为 subgraph 内部切分

`src/partition.rs` 的思路是：给定一个已经 selected 的 subgraph，枚举内部 tensor edge 是否 retained，
然后用这些 retained edges 把原 subgraph 切成一条 partition chain。

`try_extract_output_covering_subgraph` 从待覆盖 outputs 反向走 producer：

- 遇到 subgraph input 停止；
- 遇到 marked retained edge 时，把 tensor 记为这一段需要的 retained tensor，并停止继续向上；
- 然后从 retained tensor 的 consumers 向下扩展，保证相关 outputs 被覆盖。

`try_partition_subgraph` 反复提取 covering subgraph，直到 outputs_to_cover 为空，再反向组装 partitions，并为每段重新
`search_tile_values` 和 `subgraph_latency`。

### 8.2 Beam search over retained edges

`search_partition` 收集 subgraph 内部非输入 edges，把每条 edge 的 retain decision 作为布尔变量，beam size 固定为 10：

```text
beam = [(assignment, cost)]
for edge in internal_edges:
  expand retain=true / false
  try_partition_subgraph
  keep 10 lowest-cost feasible assignments
```

如果某一步没有 feasible candidates，则构造一个到当前 edge 为止全 false 的 assignment 作为保守路径。

对 CIM 的启发是：retention 可以作为边级决策逐步搜索，而不是一次性枚举所有 retained tensor set。对本项目生产策略而言，需要把“保守路径”改成明确合法主线，而不是宽容 fallback。

### 8.3 与 VNRC coupling 的差别

第三名项目的 retention partition 是 selected subgraph 内部的局部 beam；VNRC 的 coupling 是 selected groups
之间的显式 retained chain，并且 coupling move 与 partition move 同时竞争。

因此第三名更简单，适合早期实现；VNRC 更强，适合后续让 residency 反向影响 structural partition。

## 9. Output 与 baseline

`src/output_format.rs` 输出：

- `subgraphs`；
- `granularities`；
- `tensors_to_retain`；
- `traversal_orders`；
- `subgraph_latencies`。

`src/naive_scheduler.rs` 提供逐 op baseline：每个 op 单独作为 subgraph，选最大可行 tile，不做 inter-op retention。
`main.rs` 的 `--compare-naive` 会输出 naive total、optimized total 和 speedup。

writeup 报告五个 public benchmarks：最大收益在 `mlsys-5`，其它 benchmark 收益较小。这与方案特性一致：
如果图里有足够 pointwise fusion neighborhood，convex fusion + retention partition 才能明显降低 memory traffic。

## 10. Tests 反推的设计覆盖

测试分布在各源码模块内：

- `graph.rs`：topological sort、subgraph set algebra、components、output tensors；
- `tiling.rs`：official examples、native cap、mixed PW→MM 几何约束、k cap、traffic minimization；
- `performance_model.rs`：official examples、retained output、selective residency、snake、split-k；
- `global_optimization.rs`：chain / diamond / fanout / recomputation / partial fusion BLP cases；
- `partition.rs`：Example 3 selective residency 与 flash recomputation；
- `naive_scheduler.rs`：baseline smoke。

这套测试比 VNRC 少，但比 first-place 源码更能看出数学优化意图。对 CIM 仍不应照搬为长期测试矩阵；可借鉴的是端到端 gate 的覆盖点：convex legality、tile feasibility、retention visibility、recompute dependency、输出 schema。

## 11. 对 CIM-compiler-design 的可借鉴点

### 11.1 Convex subgraph 是很好的第一版候选约束

CIM 第一版 execution-subgraph candidate 可以从 connected-convex 开始，减少非法 fusion。它自然适配 Flow dispatch boundary 与 MLIR region/cluster 思维。

### 11.2 BLP 适合做离线或 bounded backend

BLP 能表达：

- 选择哪些 cluster；
- 是否允许 recomputation；
- graph output coverage；
- producer dependency；
- 目标函数最小化 cost。

对 CIM，它可以作为后续 backend，但第一版不一定要引入外部 LP solver。若引入，必须清楚 solver 预算、失败语义、license/build 风险与 verifier 边界。

### 11.3 Retained context 必须影响 tile search

第三名项目在 `search_tile_values` 里扣除 retained tensor 容量，说明 retained values 不是 output annotation，而是 tile feasibility 输入。CIM 也必须让 SRAM residency 影响 tile、bank、copy、barrier 与 timeline choices。

### 11.4 Slice-level residency 比 tensor-level 更精确

`SliceName` / `ResidencySet` 的 partial slice 模型适合 CIM：很多 CIM dataflow 复用的是 weight row-strip、activation tile、partial-sum block，而不是整个 tensor。

### 11.5 Exact arithmetic 与 normalized cost terms

`Fraction` 在竞赛例子中避免了浮点误差。CIM 不一定需要全程 exact arithmetic，但应该稳定 cost terms，并避免把单位混在 f64 黑盒里。

## 12. 不应照搬的点

1. **不要把 BLP 作为唯一主线**：外部 solver 增加依赖、构建、时间预算与失败语义复杂度。
2. **不要把轻量 `Subgraph` 直接当 CIM execution object**：CIM 需要 boundary/ephemeral/retained/carrier projection 语义。
3. **不要固定 snake traversal**：CIM dataflow 更复杂，traversal 应是候选或 cost-model 输入。
4. **不要保留宽容 fallback**：生产路径应拒绝非法 planning/projection，而不是自动改成 all-false retained assignment。
5. **不要让 output JSON 思维污染 runtime ABI**：竞赛 schedule JSON 只是评分格式，CIM runtime facts 必须由 owner carriers 提供。

## 13. 推荐落地顺序

1. 在 CIM planning service 里实现 connected-convex candidate generator。
2. 为每个 candidate 建立 execution-subgraph evaluator，而不是只保轻量 op set。
3. 实现 slice-level SRAM residency model：whole vs partial、adjacent reuse、accumulator lifetime。
4. 先用 bounded beam / priority queue，不急于引入 BLP。
5. 在 selected candidates 稳定后，再评估小型 BLP backend，用于 recomputation-aware selection。
6. 将 retention edge search 限制为相邻 stage，并要求可投影到 owner carriers。
7. 用少数端到端 gate 验证：convex fusion、selective residency、recompute、illegal projection rejection。
