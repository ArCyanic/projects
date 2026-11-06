# 1　全局图优化：合并独立异构 MVM

在 ONNX 导入到 Linalg 阶段后，程序仍处于通用高层张量表达。此时计算图尚未被 IREE 划分调度边界（Dispatch），所有算子间的数据依赖全局可见，是执行跨分支图级改写的唯一窗口。

---

## 1.1 为什么需要全局图优化

CIM 硬件的单次 MVM 调度以阵列列宽（$C=512$）为单位。当模型中存在多个输出通道较窄且互不依赖的矩阵乘时，分立执行会导致阵列有效列利用率极低，且触发多次 Dispatch 切换与重复位串行展开。

全局图优化通过识别同一基本块内的独立候选，将其输入张量沿 K 维拼接、静态权重重构为分块对角矩阵，合并为单次宽向量计算。

```
[ 分立分支计算 ]                  [ 块对角融合计算 ]
X0 · W0 ──> Y0                    [X0 | X1] · diag(W0, W1) ──> [Y0 | Y1]
X1 · W1 ──> Y1                                                 ├──> ExtractSlice ──> Y0
                                                               └──> ExtractSlice ──> Y1
```

---

## 1.2 融合改写

标准 `extendPreprocessingPassPipeline` 直接由 `CIMFuseHeterogeneousContractionsPass` 对标准位宽的 `linalg.matmul` 做块对角重写，再调用原生横向 contraction 融合。这里的“全局图优化”指图级作用域；实际接入点是 IREE preprocessing，无需增加 global-optimization hook。

```text
[ CIMFuseHeterogeneousContractionsPass ] ── DAG 切片分析、容量试排与块对角重写
           │
           ▼
[ Dispatch Creation ]
```

### 候选的语义前提

候选必须是静态 rank-2、零初始化的 signed 整数乘加，activation/output maps 分别为
`(m,k)` 与 `(m,n)`。检查同时覆盖原生 `cast` 属性与标量 region；只确认 contraction
接口不足以排除 unsigned、其他乘加语义或转置 activation。静态权重清单同时支持
Dense 与 DenseResource 常量，并保留 RHS map/显式 transpose 所表达的 K/N 方向。

### DAG 依赖切片与拓扑调度
调用 `mlir::getBackwardSlice` 为所有候选构建依赖集：
- 候选必须位于同一 `mlir::Block`；
- 输入激活值必须是不同 SSA 变量（共享激活值的留由 Dispatch 之后的 Horizontal Packing 处理）；
- 候选间不得存在前后依赖关系；
- 插入点取组内最靠前的矩阵乘，再用 MLIR 原生 `moveValueDefinitions` 把尚未支配该点的 activation 定义及其依赖移过去；旧 weight/init 将由新的 constant/fill 取代，无需搬运。

依赖集直接保存在候选中。由于切片限制在同一 block，SSA 定义先于使用，沿 IR 逆序即可
从 consumer 向 producer 计算下游深度。组的优先级统一表示为
`(节省窗口数, -下游深度之和, 成员数)`，按字典序比较；同分时保留原来的稳定遍历顺序。

### 成本收益与全局容量检查
成组改写必须同时满足两个硬性条件：
1. **窗口收益**：合并后的总列窗口严格少于各分立分支窗口之和：
   $$\sum_{i} \left\lceil \frac{N_i}{512} \right\rceil > \left\lceil \frac{\sum N_i}{512} \right\rceil$$
2. **阵列容纳能力**：总行数 $\sum K_i \le 1024$，且合成块对角权重与模块内其他全部静态权重共同通过 `planStaticArray` 放置试排。

每轮 IR 改写之前，先按 IR 顺序解码完整静态权重清单，候选引用这份只读清单。试排只替换
待融合组对应的权重，不重新遍历 IR。不能改进本轮最佳增益的候选先被跳过；完成一次
`rewriteGroup` 后，再重新建立清单与依赖，避免复用失效的分析结果。

---

## 1.3 IR 改写模式

当候选组被判定为可行且有收益时，Pass 执行以下结构性重写：
1. 使用 `tensor.concat` 沿 K 维拼接激活张量 $\tilde{X}$；
2. 构建包含对角有效权重与非对角结构零的常量矩阵 $\tilde{W} = \operatorname{diag}(W_0, W_1, \dots)$；
3. 生成单次矩阵乘 $\tilde{Y} = \tilde{X} \tilde{W}$；
4. 使用 `tensor.extract_slice` 从 $\tilde{Y}$ 中按原始列宽切出各自分支的结果，无缝替换原有算子的所有使用点。

