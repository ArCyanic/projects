# 基于 IREE 原生阶段的 CIM 编译管线

本文以 `IREEVMPipelinePhase` 定义的 12 个原生阶段为坐标，记录 CIM 编译器的介入点和阶段边界。按程序演化顺序学习这些变换，见 [CIM 编译流程](guide/README.md)；IREE 各阶段的源码入口和原生职责见 [IREE VM Pipeline 阶段功能划分](iree-study/iree-vm-pipeline-stages.md)。

## 全局坐标

| 顺序 | IREE 原生阶段 | IREE 的阶段职责 | CIM 在该阶段的工作 |
| ---: | --- | --- | --- |
| 1 | `input` | 将前端方言转换为 IREE 接受的张量程序 | 规范化 ONNX 线性算子，消除前端表达差异 |
| 2 | `abi` | 包装入口函数并建立调用约定 | 无自定义 pass |
| 3 | `preprocessing` | 执行用户或插件显式指定的预处理 | 执行可选的异构块对角融合，再调用原生横向 contraction 融合 |
| 4 | `global-optimization` | 在创建 dispatch 前优化全程序张量计算 | 沿用原生全局优化，不增加阶段 hook |
| 5 | `dispatch-creation` | 融合候选计算并形成 `flow.dispatch` 边界 | 原生 dispatch formation 消费预处理后的 contraction；无自定义 hook |
| 6 | `flow` | outline dispatch，形成 `flow.executable` | 沿用 IREE 的 outline 和常量捕获；不插入自定义 pass |
| 7 | `stream` | 建立资源、时间线、并发和命令调度 | 沿用 IREE 调度；不插入自定义 pass |
| 8 | `executable-sources` | 分配设备并物化 HAL executable 接口 | 注册 CIM target、硬件 profile 和 executable format |
| 9 | `executable-configurations` | 为 executable 选择目标相关的翻译策略 | 选择 CIM lowering pipeline，确定 workgroup 划分和合法的 Array tile |
| 10 | `executable-targets` | 将 executable 翻译为目标 IR | 完成 tiling、二维合法化、bufferization，并生成逻辑 CIM IR |
| 11 | `hal` | 转换 host program，链接并序列化 executable | 在链接后的完整部署上完成权重排布、Array 规划、SRAM 管理、bit-serial 展开和序列化 |
| 12 | `vm` | 将 host-side HAL 程序降低为 VM module | 沿用 IREE VM lowering；CIM executable 已封装为 binary |

```text
ONNX
  │
  ├─ input ───────────────────── CIM 线性算子规范化
  ├─ abi
  ├─ preprocessing ───────────── 可选异构融合 → 原生横向融合
  ├─ global-optimization ─────── IREE 原生张量优化
  ├─ dispatch-creation ───────── IREE 原生 dispatch 边界形成
  ├─ flow ────────────────────── outline executable，捕获静态权重
  ├─ stream ──────────────────── IREE 资源与时间线调度
  ├─ executable-sources ──────── 绑定 CIM target 与硬件 profile
  ├─ executable-configurations ─ 选择 lowering 策略与合法 tile
  ├─ executable-targets ──────── 二维合法化 → bufferization → 逻辑 CIM IR
  ├─ hal ─────────────────────── 链接 → 权重排布 → Array/SRAM 物理化 → 序列化
  └─ vm ──────────────────────── host program 降低为 VM module
```

## CIM 介入点

### 1. `input`：统一前端线性算子

`CIMNormalizeONNXLinearPass` 运行在插件 input conversion 中，将 Torch/ONNX 导入产生的线性算子整理为后续 IREE 优化能够稳定识别的张量计算。该阶段只处理前端语义差异，不决定 dispatch、Array 布局或 SRAM 地址。

阶段输出仍是通用的 tensor/linalg/arith IR，因而可以继续进入 IREE 原生 ABI 和 preprocessing 阶段。

### 2. `preprocessing`：异构块对角融合

`CIMFuseHeterogeneousContractionsPass` 把同一 block 中互不依赖的静态 MVM \(Y_i=X_iW_i\) 改写成一次块对角乘 \(\,[Y_0\ Y_1\ \cdots]=[X_0\ X_1\ \cdots]\,\mathrm{diag}(W_0,W_1,\ldots)\,\)，再按原来的 \(N_i\) 切回各 \(Y_i\)。候选由 `isaContractionOpInterface` 识别；改写前用 `planStaticArray` 检查完整静态权重 inventory。代数与 matcher 见 [全局图优化](guide/1-global-optimization.md)。

该变换接在标准 `extendPreprocessingPassPipeline`，使用前端直接生成的 i32 contraction，
不增加 global-optimization 插件 hook。它仍在原生全局优化与 `dispatch-creation` 之前完成。

### 3. `preprocessing` 中横向融合，`dispatch-creation` 中形成边界

CIM 在标准 `extendPreprocessingPassPipeline` 中、异构融合之后调用原生
`FuseHorizontalContractionsPass`，`fusionLimit=4`。它将共享 activation 且满足上游条件的
contraction 组织为横向融合 op；随后的原生全局优化和 dispatch formation 消费这一结构。
IREE 源码不增加 global-optimization 或 dispatch-creation 插件 hook。

预处理阶段只整理计算结构，dispatch 边界在第 5 阶段才形成。横向 Case 的 4 个 contraction
最终进入 1 个 dispatch；真正的权重拼接发生在 `hal` 阶段的链接后物理化中。
上游 `M<16` 不融合的限制保持原样，因此综合 Case 的两个 `M=1` producer 分别保留。
当前窗口与容量结果见 [消融报告](experiments/optimization-ablation-report.md)。

### 4. `flow` 与 `stream`：保留 IREE 调度语义

Flow 将 dispatch outline 为 executable，并把静态权重带入目标程序；Stream 再建立资源、时间线、并发和命令关系。CIM 不在这两个阶段插入自定义 pass，后续物理化只改写 target executable，不重排 host 侧 dispatch、barrier 或 queue 语义。

### 5. `executable-sources`：建立目标身份

CIM target backend 向 HAL 提供：

- backend：`cim`；
- executable format：`cim-executable`；
- 硬件 profile；
- 支持的整数类型。

IREE 据此完成设备分配、HAL interface 物化和 executable variant 建立。此时尚未选择具体 lowering 策略。

### 6. `executable-configurations`：选择合法执行结构

CIM configuration pipeline 为每个 executable 选择 translation pipeline，并生成 IREE 的 `translation_info` 与 `lowering_config`。配置同时确定：

- workgroup 覆盖的 M 范围；
- Array 的 M/N/K tile；
- 超出单次 Array 覆盖范围时的整数二维切分。

配置结果仍由 IREE Codegen 属性承载，供下一阶段的目标翻译使用。当前合法化只接受能够整数切分的形状，不引入 padding 路径。

### 7. `executable-targets`：从 dispatch 计算到逻辑 CIM IR

CIM translation pipeline 在 IREE 的 target executable 内依次完成：

```text
workgroup tiling
  → linalg 分解
  → Array M/N/K 二维合法化
  → 横向融合 GEMM 分解
  → dispatch tensor bufferization
  → comprehensive bufferization
  → linalg-to-CIM conversion
  → 原生 annotated-loop 全展开与规范化
```

阶段输出是 workgroup-parametric、Array-legal 的逻辑 `cim.mvm`/`cim.elt` 程序。入口保持原生无参数函数，binding 和 workgroup 坐标继续由 HAL interface 操作表达，直接在序列化时消费。串行 K tile 由结构化循环和 view 表达：每个 K tile 产生一个 MVM partial，再通过显式 `cim.elt add` 累加。`cim.mvm` 本身保持 overwrite-only 语义。

### 8. `hal`：在完整部署上完成物理化

IREE 先把 host program 转换到 HAL，再调用 target backend 的 linking hook。链接后的 module 同时包含该部署的全部 CIM executable 和静态权重，因此权重排布、容量判断和存储分配都在这里完成。

```text
IREE native executable linking
  → 可选的横向 MVM packing
  → 可选的权重 replication
  → 全部署 Array 规划与静态权重放置
  → SRAM copy 和 scratch 物化
  → bit-serial 展开
  → SRAM lifetime 分配
  → affine 地址降低与规范化
  → executable serialization
```

这一阶段拥有以下物理事实：

- Array planner 对 linked variant 的全部静态权重统一去重、切分和确定性放置；
- 全部权重驻留在一个 Array root 的固定矩形 region 中；
- 唯一的 `__cim_array_init` export 负责部署期写入，compute export 只访问已驻留 region；
- packing 和 replication 复用同一个全部署容量检查，只有可放置的候选才会进入物理程序；
- boundary import/export 和 SRAM 内部搬运保留为原生 `memref.copy`，直接序列化成 transfer record；
- 每个逻辑 `cim.mvm` 展开为 `cim.bit` 与 `cim.elt` 重建，并获得真实 SRAM scratch；
- SRAM allocator 对 activation、partial result 和 scratch 统一分配，可选择顺序布局或 lifetime reuse。

序列化器从同一份物理程序生成 `hal.executable.binary`。二进制 payload 是运行时输入；比赛要求的 `.cim.isa` 是同一程序的文本投影。两者的格式分别由 [CIM executable payload 规范](spec/cim-executable-payload-spec.md) 和 [CIM ISA 规范](spec/isa/cim-isa-spec.md) 定义。

### 9. `vm`：完成 host 侧编译

CIM executable 在进入 VM 阶段前已经链接并序列化。IREE 原生 VM pipeline 继续降低 host 侧控制流、HAL 调用和资源初始化；CIM runtime 从 `hal.executable.binary` 读取 payload 并执行其中的部署期与运行期 program。

## 两组容易混淆的优化

| 优化 | IREE 坐标 | 改写对象 | 目的 |
| --- | --- | --- | --- |
| 异构块对角融合 | `preprocessing` | tensor 计算图与静态权重 | 合并输出形状不同的 contraction |
| 横向 contraction 融合 | `preprocessing` | contraction 与 dispatch 边界 | 让共享输入的计算进入同一 dispatch |
| 横向 MVM packing | `hal` linking hook | linked logical CIM program 与权重 | 把同一 dispatch 内的 MVM 排入同一物理执行窗口 |
| 权重 replication | `hal` linking hook | linked logical CIM program 与权重 | 用 Array 容量换取更少的 bit rounds |

前两项改变高层计算组织，后两项改变链接后的物理权重排布。这个边界使 IREE 继续负责 dispatch 和 host 调度，CIM 后端负责 Array 与 SRAM 的部署事实。
