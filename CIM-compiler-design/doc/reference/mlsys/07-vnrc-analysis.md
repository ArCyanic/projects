# MLSys 2026 VNRC Submission 分区、耦合与重算搜索解析

## 0. 一句话结论

VNRC submission 的核心不是“沿拓扑序构造一个 schedule”，而是先把算子图变成
可重算、可重叠的 `Partition`，再在 `CoupledPartition` 上显式搜索跨 group 的
fast-memory retention chain。它把 subgraph 合法性、tiling 合法性、容量可行性、
重算覆盖、ephemeral gap、group DAG 无环性都压进搜索状态和 move evaluator，
因此每一步搜索都尽量停留在合法空间内。

对 CIM-compiler-design 最有价值的不是整套 FM/evolution 工程，而是三件事：

1. **执行子图对象**同时承载 boundary / ephemeral / tile / cost 语义；
2. **结构代价**与**驻留上下文代价**分层缓存；
3. **retention / recompute / ephemeral visibility**作为主路径约束，而不是事后修补。

## 1. 资料入口与源码地图

主要入口：

- `README.md`：项目目标、目录结构、输入输出 contract、测试范围。
- `writeup/writeup.tex`：两层搜索、FM、evolution、symmetry、coupling 的算法叙述。
- `src/pipeline/main.cpp`：命令行入口、竞赛时间预算推导、`solve`/`solve_v2` 调用。
- `src/pipeline/solver.h`：顶层三阶段 pipeline 注释。
- `src/pipeline/solver.cpp`：并行分区搜索、候选池构造、耦合搜索的实际控制流。
- `src/pipeline/evaluate.cpp`：反向揭示输出验证 contract：subgraph、tile granularity、retain、traversal、latency。
- `test/*.cpp`：按算法机制覆盖 move、FM、coupling、recompute、ordering、symmetry、solver。

源码分层非常清楚：

```text
src/core/       Problem, DAG, Subgraph, GroupDAG, CostCache
src/partition/  Partition, group bookkeeping, local acyclicity, ephemeral-gap checks
src/init/       多策略初始化与 symmetry-driven 初始化
src/search/     local search, FM, evolution, diversity pool, coupling search
src/solution/   ordering, retain hints, final Solution validation
src/symmetry/   Merkle hashing, parallel / series pattern detection
src/pipeline/   CLI, solver pipeline, evaluator, symmetry app
```

这与上一份参考项目 `/Users/mac/repos/mlsys-2026-graph-scheduler` 的 `source/`
单层组织不同。VNRC submission 更像一份论文式 solver：每个算法层都有独立目录、
测试与命名边界。

## 2. 顶层 pipeline：先 partition，再 coupling

`src/pipeline/solver.h` 与 `src/pipeline/solver.cpp` 把求解分为三段。

### 2.1 Phase 1：并行搜索 partition pool

Phase 1 调 `parallel_search`，目标是在暂不显式搜索跨 group retain chain 的前提下
找到高质量 `Partition` 候选。输入是 `Problem`、`DAG`、共享 `CostCache`、时间预算。

其结构是：

```text
多种 init strategy
  -> greedy_descent
  -> fm_outer_loop
  -> DiversityPool admission
  -> mutation / crossover / symmetry mutation
  -> FM refine
  -> pool update
```

如果图里有 retainable tensors，Phase 1 通常只吃约 35% 总预算；如果没有 retainable
tensors，则分区搜索几乎就是主求解器，会吃掉大部分预算。

### 2.2 Phase 2：从 partition pool 生成 solution / coupled pool

Phase 2 把分区候选变成可执行顺序或耦合候选：

- 无 retainable tensor 时：finalize 最佳 partition，然后用 DFS ordering 生成 schedule。
- 有 retainable tensor 时：把多个 partition 候选提升成 `CoupledPartition`，并从 DFS /
  beam ordering 的 retain hints 里种下初始 coupling。

这里的 ordering 不是普通 topo sort。`src/solution/ordering.cpp` 同时产出：

- group 执行顺序；
- 每一步希望保留的 tensor set。

也就是说，ordering 层已经在为 retention search 生成上下文。

### 2.3 Phase 3：coupled evolution

Phase 3 在 `CoupledPartition` 上继续搜索。它不只是“先 partition，后处理 retain”，而是
让 partition moves 与 coupling moves 在同一个 FM/evolution 体系中竞争。

`src/search/coupled_fm_search.h` 的 `CoupledFMMove` 在普通 move 之外加入：

- `COUPLE`
- `UNCOUPLE`
- `RETAIN_FORCE_SPLIT`
- `FORCE_RETAIN`
- `EPHEMERAL_FUSE`

这说明 retained tensor 被编码成 group-to-group chain 的一部分，而不是松散的全局 hint。

### 2.4 时间预算是 pipeline contract 的一部分

`src/pipeline/main.cpp` 根据竞赛文件名推断 2s / 5s / 15s / 30s / 60s / 120s 档位，并只使用约
95% 预算，把剩余时间留给 I/O 与收尾。`writeup/writeup.tex` 也强调单一 deadline 会向
worker thread 传播。

对 CIM 的启发不是照搬竞赛时间档，而是：whole-graph planner 应该把预算显式传进搜索、
cost cache、并行 worker 与候选池策略，而不是让各层自行猜测何时停止。

## 3. 核心数据模型

### 3.1 `Problem`、`TileConfig`、`CostResult`

`src/core/types.h` 定义基础 contract：

- `Problem`：全局张量、算子、fast memory 容量、slow memory 带宽、native tile 上限、
  retainable tensors。
- `TileConfig`：`w / h / k / snake`。
- `CostResult`：`feasible / latency / working_set / num_spatial_tiles / num_k_passes /
  compute_per_step / config`。

这个分层很干净：`Problem` 是硬件与图事实，`TileConfig` 是局部执行选择，`CostResult` 同时
返回可行性与代价。

### 3.2 `DAG`：依赖图与局部聚类邻接分离

`src/core/dag.h` 和 `src/core/dag.cpp` 维护：

- tensor producer / consumers；
- op predecessors / successors；
- topo order / topo position；
- reachability bit matrix；
- longest chain；
- `op_neighbors`。

关键点是 `op_neighbors` 不只包含 DAG 边，也包含共享输入 tensor 的 co-consumer 关系。这样
DAG 依赖和“适合聚类的邻接关系”没有混在一个概念里，但可以在 partition search 时合并使用。

对 CIM 来说，这对应两类事实：

- 数据依赖：必须满足；
- 资源/复用邻接：可用于候选构造与局部搜索，但不能替代依赖合法性。

### 3.3 `Subgraph`：不是 op-set，而是执行子图

`src/core/subgraph.h` / `src/core/subgraph.cpp` 的 `Subgraph` 是 VNRC 最重要的对象。它在
`Subgraph::create` 中一次性完成：

1. boundary inputs / boundary outputs / ephemerals 分类；
2. sink 输出形状一致性检查；
3. connected sub-DAG 检查；
4. `MM -> PW` epilogue 和 `PW -> MM` prologue 几何约束推导；
5. `output_K_ / max_K_` 推导；
6. tile divisibility sets；
7. boundary tensor tile-source 反向传播；
8. ephemeral accumulator 与内部张量 footprint 推导。

因此这里的 `Subgraph` 已经带有执行语义。它不是“候选 cluster 的名字”，而是一个可被 tile、
可被计费、可被验证的执行单元。

这非常适合 CIM 参考：CIM 的执行子图也不应只是 op 集合，而应携带 SRAM 可见性、tile/source
约束、局部 dataflow、accumulator 生命周期和可投影 carrier 的事实。

### 3.4 `Partition`：不是纯划分，而是带重算的覆盖

`src/partition/partition.h` 明确说明 `Group` 可以 overlap，代表 recomputation。`Partition` 维护：

- alive groups；
- 每个 group 的 `ops / cost / sg / best_cfg`；
- group DAG；
- op 到 groups 的反向索引；
- tensor 到 materializing group 的索引；
- 多种局部 acyclicity checks；
- ephemeral gap checks。

这意味着 partition 的语义不是“每个 op 恰好归属一个 group”，而是“每个 op 至少被覆盖，
某些 op 可以在多个 group 中重算”。

对 SRAM 紧张的 CIM 场景，这是很重要的建模方向：重算不是错误处理，而是一种可搜索、可计费、
可验证的资源规划选择。

### 3.5 `GroupDAG`：重算依赖的 OR-semantics

`src/core/group_dag.h` / `src/core/group_dag.cpp` 为 group-level dependency 提供增量检查。
它的重要注释是 recomputation 的 OR-semantics：一个 consumer 需要的 tensor 若有多个 producer
copy，只要存在一个 producer group 能在 consumer 前执行即可。

这比普通 DAG edge 更接近 CIM 的实际规划：同一逻辑值可能来自重算、SRAM retained、DRAM
materialization 或其他 carrier。调度依赖不应过早压成单一 producer edge。

### 3.6 `CoupledPartition`：把 retained tensor 变成链式边

`src/search/coupling_search.h` 定义 `CoupledPartition`：

- 包含一个基础 `Partition`；
- `next_group` / `prev_group` 描述 coupling chain；
- `retained[(ga, gb)]` 描述从 group `ga` 到 group `gb` 保留的 tensor set；
- 每个 group 最多一个 incoming 和一个 outgoing coupling edge。

这个“一入一出”的限制把 coupling 限制成 disjoint paths，显著缩小搜索空间。它牺牲一部分表达力，
换来可控的 move 评估和链式上下文重算。

## 4. 约束表达：legal state first

### 4.1 Subgraph 合法性

`Subgraph::create` 不是简单构造函数，而是合法性入口。它检查：

- op set 非空且有 boundary output；
- sub-DAG connected；
- sink 输出 `(W,H)` 一致；
- 内部 ephemeral 与外部 boundary 不冲突；
- mixed MM/PW 模式满足几何限制；
- boundary tensor 的 tile-source 可推导。

如果无法形成这样的执行语义，候选就不应该进入后续 cost search。

### 4.2 Tile 合法性与容量可行性分层

`Subgraph::is_valid_tiling` 处理 tile/shape/geometry 合法性：

- `w / h / k` 正数；
- 不超过 native cap；
- 满足 `w_divides_ / h_divides_ / k_divides_`；
- boundary tensor 的 tile-source 不越界；
- ephemeral slice 尺寸满足内部约束。

`working_set_unchecked` 和 `is_feasible` 再处理 fast memory 容量。也就是说：

```text
tile / geometry legal
  -> working-set fits fast memory
  -> latency computation meaningful
```

对 CIM 应保持同样分层：ISA/映射合法性、SRAM/阵列资源可行性、性能代价不能混成一个布尔值。

### 4.3 Acyclic 检查集中化

VNRC 同时有局部 cheap check 和全局 Kahn check：

- `src/core/dag.*`：op 级 reachability；
- `src/core/group_dag.*`：group 级增量可达性；
- `src/search/feasibility.h` / `.cpp`：`MoveDelta` 与 `kahn_with_delta`。

`src/search/feasibility.h` 的注释强调 partition-level cycle checks 归这里管，search 文件不应自行实现
另一套 cycle logic。

对 CIM 很关键：legality oracle 必须集中，不能在每个 pass 或 search move 里复制一棵 validator/helper tree。

### 4.4 Ephemeral-gap 约束

`Partition::creates_ephemeral_gap`、`Partition::split_creates_ephemeral_gap`、
`Solution::creates_ephemeral_gap` 共同维护一个语义：

> 如果 tensor 被某个 subgraph 当作 ephemeral，它就没有自动跨边界可见性；外部消费者必须由
> boundary materialization、retention 或 recomputation 覆盖。

这正是 CIM SRAM 生命周期需要的约束。片上 scratch 值不是公共 contract；跨 stage 可见性必须由
明确 carrier 或重算策略提供。

## 5. Cost model 与 cache

### 5.1 单 group cost 数据流

基础 cost 流是：

```text
Partition::eval_set
  -> CostCache::evaluate
  -> Subgraph::create
  -> Subgraph::best_cost
  -> Subgraph::is_valid_tiling
  -> Subgraph::working_set_unchecked
  -> Subgraph::compute_cost
```

`Subgraph::best_cost` 枚举 `TileConfig`，找到可行且 latency 最小的配置。不可行 group 直接返回
高代价，不进入优质候选。

### 5.2 Latency 不只是 compute + bytes

`Subgraph::compute_cost` 把 IO 拆成多个类别：

- once load；
- row load；
- col load；
- tile load；
- stream load；
- output eviction。

然后按照 traversal pattern 合成，尤其区分 row-major、col-major、snake 等遍历方式。这说明空间
遍历顺序本身就是 cost model 输入。

对 CIM 来说，dataflow、scan order、bank reuse、weight stationarity、partial-sum residency 也必须
是代价模型的一部分，而不能只看静态读写量。

### 5.3 Split-k 与 accumulator 生命周期

`TileConfig::k`、`num_k_passes`、`compute_per_step` 与 split-k latency 公式共同表达 accumulator
生命周期。VNRC 在 closed-form cost 里处理 split-k，而上一份参考项目更强调 tile-time simulation 中的
accumulator 事件。

两者对 CIM 都有价值：

- 若硬件行为足够规则，可用 VNRC 式 closed-form；
- 若 accumulator / SRAM / DMA 时序更复杂，上一份参考项目的 tile simulator 更稳。

### 5.4 `CostCache`：结构缓存与上下文缓存分层

`src/core/cost_cache.h` 有两层：

- base map：`op_set -> CostResult`；
- retention map：`op_set + entering + retain -> CostResult`。

这正好对应 Phase 1 与 Phase 2/3：先评估 group 自身，再评估带驻留上下文的 group。

CIM planner 也应类似拆分：

```text
cluster structure cost
  != same cluster under SRAM/bank/retained context cost
```

否则搜索会把上下文敏感代价错误缓存成全局常量。

## 6. Search：move-rich FM + evolution

### 6.1 初始化是多策略的

`src/init/init_strategies.cpp` 包含多种起点：

- trivial；
- chain-then-edge；
- seed-and-grow；
- reverse-topo；
- tensor-aligned；
- random。

`src/init/symm_init.cpp` 还用 symmetry / series patterns 做初始化，把同构结构的局部选择复制到
其他副本。

对 CIM，规则网络块、重复 stage、阵列重复结构都可能从 symmetry-driven init 受益。

### 6.2 FM move 不只是 move/cut

`src/search/fm_search.h` 的 `FMMove` 类型包括：

- `STEAL`
- `EJECT`
- `RECOMPUTE`
- `MERGE`
- `INTERNAL_EJECT`
- `SPLIT`
- `TENSOR_MERGE`
- `TENSOR_EXTRACT`
- `DE_RECOMPUTE`
- `FORCE_RECOMPUTE`
- `TENSOR_EXTRACT_SPLIT`

`best_move_for(op)` 为每个 initiating op 找当前最佳动作，`ActiveSet` 只维护每个 op 的最佳 move，
而不是把所有候选动作都常驻堆中。这是规模控制的关键。

### 6.3 Gain 是真实 cost delta

`src/search/partition_moves.cpp` 的 `eval_*` 基本以 `old_cost - new_cost` 形式计算 saving。复杂 move
会先用 `connected_components`、`analyze_split`、ephemeral-gap check、acyclic check 筛掉非法情况，
再重新评估受影响 groups。

这比抽象图划分里的 cut-gain 更贴近硬件规划：move 是否值得做取决于 tile、capacity、retention、
recompute 后的真实代价。

### 6.4 FM drift 与 evolution 共同避免局部最优

`src/search/fm_pass.h` / `.cpp` 和 `src/search/fm_outer.cpp` 提供 drift budget、floor、连续不提升次数、
cosine cooling、deadline 等控制。FM 允许短期变差，但保留 pass 中出现过的最佳 partition。

`src/search/evolution.cpp` 再提供 mutation 与 crossover：

- merge / split / reassign / eject；
- tensor merge / de-recompute / force recompute；
- compound mutation；
- agreement-based crossover；
- DAG-cut crossover。

### 6.5 `DiversityPool` 保留质量与结构多样性

`src/search/pool.h` 的 `DiversityPool` 不是只保最优。它有 near-duplicate rejection、diversity-aware
eviction、softmax selection、negative assortative mating。普通 partition 距离用 ARI；coupled partition
距离混合 ARI 与 retained-tensor Jaccard。

这对 CIM 很有启发：全局资源规划很容易早熟收敛到单一 fusion/tile 形态，候选池需要显式维护结构多样性。

## 7. Coupling：retention 是搜索层，不是输出装饰

### 7.1 Chain 限制缩小了状态空间

`CoupledPartition` 限制每个 group 最多一个 incoming 和一个 outgoing coupling edge。这让 retained
关系形成 disjoint chains，而不是任意图。好处是：

- entering context 容易定义；
- retain set 只和相邻 coupling edge 绑定；
- group cost 的上下文重算范围可控；
- invalidation 简单。

### 7.2 Coupled FM 把结构 move 与 retain move 放在同一竞争面

`src/search/coupled_fm_search.cpp::best_coupled_move_for_op` 会同时考虑普通 partition move 和 coupling
move。原因是 retained context 会改变一个 group 的最优 tile config 与 latency，不能把 retain search
放到最后单独做。

这点对 CIM 很重要：如果两个 dispatch 共享 SRAM buffer，会改变两边的 tile、bank、copy、barrier、
occupancy 选择。跨 stage residency 必须参与主搜索，而不是 schedule 完成后的 annotation。

### 7.3 Ephemeral-fuse 与 force-retain 的意义

`EPHEMERAL_FUSE`、`FORCE_RETAIN`、`RETAIN_FORCE_SPLIT` 说明 VNRC 允许为了 retain 一个 tensor 而改变
分组边界。换句话说，数据可见性需求可以反过来驱动结构划分。

CIM planner 也应允许：

- 为保留 accumulator 或 weight tile 调整 cluster 边界；
- 为避免 DRAM materialization 引入重算；
- 为片上 residency 改变 dispatch cut。

但这些只能作为 planner 内部事实，最终必须投影到 MLIR/IREE owner carriers，而不能成为 sidecar contract。

## 8. Tests 反推出来的设计原则

VNRC tests 不是简单接口测试，而是算法机制测试：

- `test/local_search_test.cpp`：greedy move、ephemeral gap、cache、严格改进。
- `test/fm_search_test.cpp`：FM drift、lock、active set、cycle checks。
- `test/coupling_test.cpp`：coupling chain、retain edge、force split、force retain、ephemeral fuse。
- `test/coupled_fm_correctness_test.cpp`：coupled FM move 正确性。
- `test/recompute_correctness_test.cpp`：recompute / de-recompute 与 coupling invalidation。
- `test/ephemeral_retain_test.cpp`：ephemeral tensor 如何通过 retain 变得可行。
- `test/ordering_test.cpp`：DFS / beam / random ordering 与 retain hints。
- `test/symm_init_test.cpp`：symmetry init 的收益与 cache 预热。
- `test/parallel_search_test.cpp`：分区池多样性、排序、deadline 行为。
- `test/solver_test.cpp`：端到端有效性、覆盖性、MM+PW step 约束、coupling search。

对 CIM，本仓库的测试策略要求更激进地收缩测试矩阵，只保留少数黑盒/端到端 gate。因此不应照搬 VNRC
的大量机制测试作为长期 contract。但可以借鉴它们暴露的验收点：覆盖所有 op、无非法可见性、无非法 tile、
无非法 group DAG、输出可由 owner carrier 表达。

## 9. 与上一份 MLSys graph scheduler 的主要差异

上一份参考项目 `/Users/mac/repos/mlsys-2026-graph-scheduler` 的核心模式是：

```text
GraphInfo / candidate generator
  -> beam ScheduleState expansion
  -> retention policy ranking
  -> tile-time simulation evaluator
  -> hard pruning
```

VNRC submission 的核心模式是：

```text
Subgraph semantic object
  -> Partition with recomputation overlap
  -> FM / evolution / diversity pool
  -> CoupledPartition retention chains
  -> ordering / solution validation
```

关键差异：

| 维度 | first-place graph scheduler | VNRC submission |
| --- | --- | --- |
| 主搜索对象 | `ScheduleState` / beam state | `Partition` / `CoupledPartition` |
| retention 表达 | policy + retained resident tensors | 显式 group-to-group coupling edge |
| 候选构造 | 少量模板 + beam expansion | 多 move FM + evolution + crossover |
| 合法性风格 | tile simulator 验证候选 | Subgraph / Partition / Coupling 分层合法性 |
| 代价模型 | 显式 tile-time simulation | closed-form traversal / roofline cost |
| 多样性 | beam 宽度与去重 | DiversityPool + ARI/Jaccard distance |
| symmetry | 不是公开主轴 | 初始化、mutation、canonical distance 的一等输入 |

两者不是互斥方案。对 CIM 早期版本，更稳的是采用 first-place 的小搜索空间与 simulator 思想；对后续扩展，
VNRC 的 partition/coupling/recompute 模型更适合表达复杂 residency 与 rematerialization。

## 10. 对 CIM-compiler-design 的可借鉴点

### 10.1 建立执行子图对象，但保持 transient

可以借鉴 `Subgraph`，在 CIM planning service 内部建立 transient execution-subgraph object，承载：

- op set；
- boundary inputs / outputs；
- SRAM-local ephemerals；
- tile/source constraints；
- accumulator / partial-sum lifecycle；
- cost terms；
- selected carrier projection facts。

但它不应成为 runtime ABI，也不应被序列化成 sidecar 权威文件。

### 10.2 用 boundary / ephemeral / retained 三分法表达可见性

CIM 规划中可把张量值分成：

- **boundary-visible**：可以由 Flow/Stream/HAL/bufferization carrier 表达的跨边界值；
- **ephemeral**：仅在执行子图内部可见的 SRAM scratch / accumulator；
- **retained**：跨相邻 stage 保持片上可见，需要投影成明确 alias、memory-space、barrier、timeline 或 HAL facts。

这比“所有 tensor 都是 buffer”更精确，也更符合 AGENTS 中禁止 debug/provenance sidecar 参与生产 contract 的方向。

### 10.3 原生支持 rematerialization

重算应进入 planner 的主策略空间：

- 同一逻辑值可有多个 producer copy；
- consumer dependency 采用 OR-semantics；
- 重算有明确 cost；
- selected result 仍需投影成 owner carrier。

这能覆盖 competition profile：当前主线是单 array、受限 SRAM、简单 timeline，不需要另建 planner。

### 10.4 Cost cache 分两层

建议 CIM planning cache 至少区分：

```text
cluster/op-set base mapping cost
cluster/op-set + residency/bank/retained context cost
```

第一层支持快速 structural search；第二层支持跨 stage SRAM residency search。不要把上下文敏感 cost 缓存成无上下文 cost。

### 10.5 保持 legality oracle 集中

VNRC 的 `feasibility.h` 把 Kahn-with-delta 收口到一个地方。CIM 也应把：

- DAG acyclicity；
- memory-space legality；
- SRAM capacity；
- bank conflict；
- accumulator lifetime；
- cross-dispatch visibility；
- owner carrier projection legality；

收口到少数 oracle，而不是让各 pass 自己填默认、猜测、修复或绕路。

## 11. 不应原样照搬的点

1. **不要照搬大规模机制测试矩阵**：本项目测试策略要求少数高价值 gate，而不是每个 move 的形状快照。
2. **不要照搬三阶段竞赛时间预算**：CIM planner 应按 compiler pipeline 和目标 profile 设预算。
3. **不要把 coupling chain 当成最终 ABI**：它是 transient planning evidence，最终事实必须落到 Flow/Stream/HAL/memref/target ops。
4. **不要先引入完整 FM/evolution 工程**：早期 CIM 更需要小候选空间、强 legality、可验证 projection。
5. **不要保留竞赛 solver 中的保底/宽容路径**：生产路径应拒绝非法 contract，而不是在后端修复。
6. **不要把 hash-only cache 当成 verifier**：VNRC 为竞赛性能用了 hash-only map；CIM 的 public contract 仍需 owner carrier 与 verifier。

## 12. 推荐落地顺序

1. **先定义 transient execution-subgraph 数据结构**：boundary / ephemeral / retained / tile constraints / cost terms。
2. **实现 legality + feasibility 分层 oracle**：先拒绝不可表达状态，再评估容量与代价。
3. **做小候选生成**：chain、producer-consumer、pointwise epilogue、weight-stationary block，先不做完整 FM。
4. **引入上下文 cost cache**：base cost 与 residency-context cost 分层。
5. **把 retention 做成主搜索维度**：从相邻 stage retained tensor 开始，避免全图任意 retain。
6. **验证 projection**：selected facts 必须落入现有 owner carriers，runtime 不读 planning evidence。
7. **后续再评估 FM/evolution**：只有当小候选 + simulator 不够时，再引入 VNRC 的 move-rich 搜索。
