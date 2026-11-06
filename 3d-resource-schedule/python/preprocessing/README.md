# Preprocessing

唯一入口：

```bash
PYTHONPATH=python python -m preprocessing.run mixtral --output-dir artifacts/inputs/mixtral-seed0
PYTHONPATH=python python -m preprocessing.run deepseek-v2-lite --output-dir artifacts/inputs/deepseek-v2-lite-seed0
PYTHONPATH=python python -m preprocessing.run deepseek-v3 --output-dir artifacts/inputs/deepseek-v3-seed0
```

默认生成 40,960 条正式 routes；轻量 workflow 通过 `--route-count` 缩小同一 workload。

主线由三个 module 组成：

```text
run.py      → MoEModelSpec 与 CLI
routes.py   → topic-correlated routes 与三个最终 artifacts
```

输出目录包含：

```text
model.json
activation_traces.npy
activation_trace.json.zst
```

完整实施状态与恢复点见 [`doc/archive/engineering/preprocessing-rollout.md`](../../doc/archive/engineering/preprocessing-rollout.md)。
