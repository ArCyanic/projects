# 系统设计报告构建说明

本目录专用于比赛/项目《三维存算一体 MoE 推理系统设计报告》（A4 单栏格式）交付物：

- `main.typ`：设计报告主入口文件；
- `design-report-cn.typ`：A4 单栏中文报告模板、封面排版与附录宏定义；
- `chapters/`：包含引言、问题定义、顶层设计、硬件抽象、基础设施、性能分析、权重映射与实验评估源码；
- `appendices/`：包含硬件代价推导、冻结测试和公开／合成路由对照；
- `references.bib`：设计报告引用的参考文献；
- `components.typ`：算法排版宏。

报告数据图存放于根目录 `/assets/figures/`；总体框架与三模型结果复用 `/paper/figures/` 的当前矢量图，字体位于 `/assets/fonts/`。

当前实验批次为 `build/dac-paper-full-workload/`。三模型使用约 20% 额外副本；Qwen2 与 DeepSeek-V2-Lite 使用公开路由，DeepSeek-V3 使用 seed0 合成路由。比较基线与初始化均为计入固定 Dense/MoE 工作量的均衡单副本部署。Prefill 主线为最小累计工作量，调度消融以轮转为基线。

`results.typ` 读取 `data/current-results.json`，该文件由正式汇总与原始记录计算，供报告中的表格和数值引用。`data/zero-copy.json` 保存全工作量初始化下的三方法单副本与容量放松对照，`data/high-bandwidth.json` 保存同一初始化下的 8/16/32/64 GB/s 结构量与时延。更新正式汇总与报告图：

```sh
NPU_WORKERS=8 PYTHONPATH=.:python conda run -n npu python scripts/update_design_report.py
```

此命令复用已完成的搜索、冻结测试、诊断与结构量记录。三模型测试读取 `artifacts/results/cross-model-20pct.json`，DSV3 曲线、调度消融与资源分析读取 `paper/data/results-20pct.json`。单副本结构量、三方法比较及节点热图由 `data/zero-copy.json` 生成，累计／边际收益图直接读取当前 0%–20% 包络。容量放松和高带宽扩展的本次运行输出位于 `build/design-report-restoration/`，记录导出到 `data/` 后随报告保存。QKVO 扩展读取原有 10% 冻结实验的完整测量，重画归一化速度与吞吐量，在正文图注中说明历史配置；10% 独立构造对照沿用先前清理决定。

实验章节保留单副本方法比较、固定带宽重放、节点容量与通信局部性、高带宽结构边界、复制预算与边际收益、两阶段资源分解、调度消融及映射范围扩展。数据更新沿这些分析问题补齐图表与数值。

构建命令：

```sh
typst compile report/main.typ output/pdf/design-report-cn.pdf \
  --root . --font-path assets/fonts
```

产物输出路径：`output/pdf/design-report-cn.pdf`。

收益图表统一使用归一化 Decode 速度和 Prefill 吞吐量，基线为 1。二者均由同规模的基线完成时间除以当前完成时间计算。单副本、预算、跨带宽、高带宽、调度和公开／合成对照分别在图注中说明基线；时延分解、结构量、利用率与验证／测试漂移按各自分析量展示。主图与论文共用 `plot_main_results`，每个子图仅有入选 Planar／Vertical 两条曲线，布局来源由上方区间条标出。
