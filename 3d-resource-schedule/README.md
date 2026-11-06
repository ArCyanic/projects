# 3D Resource Schedule

面向 3D CIM/PIM 硬件的 MoE 权重映射与推理延迟评估研究原型。当前结果、核验和数据图见 [RUN_REPORT](build/dac-paper-full-workload/RUN_REPORT.md)。

目标主线将问题拆为：

```text
Preprocessing
  -> Hardware capacity and compute-balanced one-copy baseline
  -> Compute-balanced / Stateful Hypergraph anchors
  -> Per-budget replication and fixed-count refinement (0%..20%)
  -> Same-budget deployment selection
  -> Frozen tests and scheduling ablations
  ├─ Decode critical-path analysis
  └─ Prefill resource analysis (T=32/128/512)
```

## 当前状态

当前正式批次位于 `build/dac-paper-full-workload/`，统一计入 Dense 与 MoE 的单副本计算工作量；DSV3 合成、DSV2-Lite 公开及合成的指定重跑已完成，Qwen2 结果和比较基线按核验复用。系统维护MoE静态权重映射、装箱、数据流调度和Decode/Prefill物理评价。

这是研究与建模原型，目前不提供稳定安装包或公共 Python API。预处理与正式实验通过封闭 CLI recipes 运行；硬件、输入和算法合同以 `doc/` 下的权威文档为准。

## Quick Start

DAC 论文实验的服务器重跑、核心数据和图表更新见 [`HANDOFF.md`](HANDOFF.md)。
环境定义在 `environment.yml`，论文实验入口为 `python -m experiments.paper_run`。

项目运行于 Python 3.14 和 Conda 环境 `npu`：

```bash
conda run -n npu env PYTHONPATH=.:python python -m pytest -q
```

`NPU_WORKERS` 统一控制进程池、Numba 与 OpenMP 的 CPU budget。macOS 默认为 8，Linux
默认为 32；独占 Linux 服务器时设置 `NPU_WORKERS=64`。实际并行度受当前进程可用 CPU
和任务数限制。

pytest 默认只运行 `tests/` 下的项目测试，不收集 `3rdparty/` 中 vendored dependencies 的 upstream tests。

日常测试使用共享的 seed0 小模型，覆盖 Planar/Vertical 执行、独立穷举参考、
资源守恒、容量约束、Decode/Prefill 路由隔离及 CLI 产物。完整模型的正式回放通过
`experiments.paper_run` 和 `experiments.comparison_baseline` 执行，步骤见
[`HANDOFF.md`](HANDOFF.md)。查看测试耗时可运行 `python -m pytest -q --durations=10`；
首次执行包含 Numba JIT 编译，后续运行复用磁盘缓存。

## 仓库结构

| 路径 | 内容 |
| --- | --- |
| `python/` | 预处理、Deployment 共享编译、Simulation 物理执行、Mapping 搜索、Profiler 指标和实验配方。 |
| `tests/` | 项目的稳定黑盒与行为测试。 |
| `doc/` | 当前问题、阶段合同、实验、硬件和成本模型文档。 |
| `doc/experiments/` | treatment、数据切片、正式结果表与 artifacts。 |
| `doc/research/` | 数学探索、失败归因、论文和非权威研究材料。 |
| `3rdparty/` | 第三方源码；不属于默认项目测试范围。 |

模块接缝与数据所有权见 [工程实现](doc/5-engineering/README.md)，静态模型、候选和执行事实各自持有明确的生命周期。

## 文档索引

- **总体研究路线图与里程碑看板**：[`doc/roadmap.md`](doc/roadmap.md)
- **权威术语字典**：[`doc/glossary.md`](doc/glossary.md)
- **数据流流水线与对象模型**：[`doc/pipeline.md`](doc/pipeline.md)
- **详细分阶段规范**：从 [`doc/README.md`](doc/README.md) 开始阅读，按映射、装箱、调度、仿真顺序组织。
- **专题研究与论文分析**：位于 [`doc/research/`](doc/research)；探索性结论以权威文档为准。

## 协作约定

- 修改前先确认对应的权威文档和活动主线。
- 不把 `doc/research/` 中的历史或探索性描述直接当作实现契约。
- 提交前运行 `python -m pytest -q`。
- Agent 协作和仓库本地规则见 [`AGENTS.md`](AGENTS.md)。
