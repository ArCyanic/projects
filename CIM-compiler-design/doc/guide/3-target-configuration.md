# 3　目标配置：选择两级分块策略

进入 `executable-configurations` 阶段时，IREE 已完成 Dispatch 调度边界的划分，各计算任务被组织为独立的目标函数。CIM 目标配置阶段（`CIMSelectLoweringStrategyPass`）的核心职责是在不改变计算语义的前提下，读取张量形状与目标硬件容量参数，为后续代码生成决策两级分块尺寸（Tiling Sizes）：
* **工作组级（Level 0 Workgroup Tile）**：决定任务实例如何切分 Batch/Token（$M$ 维），生成可在片上本地复用的多行工作组程序；
* **阵列级（Level 1 Array Tile）**：决定单次硬件 MVM 执行窗口所覆盖的最大输入行数（$K_T$）与输出列数（$N_T$）。

---

## 3.1 通用收缩算子维度推导

编译器通过 `linalg::inferContractionDims` 解析算子操作数（LHS、RHS、Init）的索引映射（Indexing Maps），提取矩阵乘的三个核心循环维度下标：
* $m$ 维：外层并行维度（Batch / Token 行数）；
* $n$ 维：输出通道维度（矩阵列数）；
* $k$ 维：乘加累加维度（归约维度）。

无论是具名矩阵乘（`linalg.matmul`），还是横向多路融合后生成的 `linalg.generic` 收缩算子，均通过该通用接口统一推导维度属性，消除了对特定前端算子形态的硬编码依赖。

---

## 3.2 阵列级分块：K/N 均匀均分准则

物理存算阵列具有固定的行容量 $C_K = 1024$ 与列容量 $C_N = 512$（8 位量化单元）。当矩阵收缩的输入行数 $K$ 或输出列数 $N$ 超出物理阵列容量时，必须进行均匀分块。

为了确保所有生成的切片具有完全相同的矩形几何特征、消除边界分支与碎片开销，分块算法在维度长度 $D$ 与硬件容量 $C$ 之间求解可行的**最小整数分块数**：

\[
p(D, C) = \min \{ q \in \mathbb{Z}^+ \mid D \bmod q = 0 \text{ 且 } D/q \le C \}, \qquad T(D, C) = \frac{D}{p(D, C)}
\]

对于权重位宽为 8 位的场景，阵列级分块尺寸固定计算为：

\[
K_T = T(K, 1024), \qquad N_T = T(N, 512)
\]

整数均分确保生成的各分块几何尺寸完全一致，为后续链接阶段的权重全局拼接与紧凑放置提供确定性的矩形输入。

---

## 3.3 工作组级分块：多行并发与复制上限协同

矩阵乘的每个 $M$ 行使用独立的激活向量与输出目标。虽然每个逻辑 MVM 在硬件执行时以单行为单位（即阵列级 $M$ 分块固定为 1），但允许一个 Workgroup 连续处理多行输入（$M_T$ 行），从而摊销任务调度开销并为后续的**权重多行复制（Weight Replication）**提供物理可能。

多行工作组尺寸 $M_T$ 受以下三项硬件物理容量严格约束：
1. **模型总行数**：$M_T \le M$；
2. **阵列输入行上限**：单阵列行数可容纳的独立激活份数，即 $\lfloor 1024 / K_T \rfloor$；
3. **阵列输出列上限**：单阵列列数可容纳的独立输出份数，即 $\lfloor 512 / N_T \rfloor$。

编译器计算可支持的多行复制上限：

\[
M_{\text{cap}} = \min \left( M, \left\lfloor \frac{1024}{K_T} \right\rfloor, \left\lfloor \frac{512}{N_T} \right\rfloor \right)
\]

随后在不超过 $M_{\text{cap}}$ 的范围内选取能够整除 $M$ 的最大因子：

\[
M_T = \text{uniformTileSize}(M, M_{\text{cap}})
\]

例如，在综合用例的横向分支中（$M=80, K=256, N=64$），$K_T=256, N_T=64$，复制上限为 $\min(80, 1024/256, 512/64) = 4$。因此编译器选择 $M_T=4$，生成网格大小为 $80/4 = 20$ 的 4 行工作组程序。

---

## 3.4 两级分块配置与管道挂载

目标配置最终将计算得到的两级分块以标准属性形式注入到根算子（Root Op）的 `#iree_codegen.lowering_config` 中：

```text
workgroup tile (Level 0) : [M_T, 0,   0]    # 仅切分外层 M 维
array tile     (Level 1) : [1,   N_T, K_T]  # M 固定为 1，切分 N 列与 K 行
```

同时，Pass 为目标函数关联 CIM 专用翻译管道标记：
```mlir
translation_info = #iree_codegen.translation_info<pipeline = #iree_codegen.pass_pipeline<"cim-workgroup">>
```

后续的目标翻译阶段将严格根据该配置展开两级循环生成与硬件合法化。
