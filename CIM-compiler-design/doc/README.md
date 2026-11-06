# 文档入口

建议按以下顺序阅读：

1. `guide/README.md`：沿 IREE 接入顺序学习完整 CIM 编译流程。
2. `architecture.md`：单阵列编译器的全局设计。
3. `pipeline.md`：精确的 IREE 阶段顺序、介入点和阶段边界。
4. `spec/README.md`：IR、payload、ISA 与 Runtime ABI 规范索引。
5. 仓库根目录 `README.md`：比赛构建、中间 IR、运行和测试；`build-run-test.md` 补充 cmake 可选加速。
6. `experiments/optimization-ablation-report.md`：消融、组合效果、成本和复现命令。
7. `design/README.md`：阶段级设计说明索引。
8. `contest-detail.md`：赛题要求与 ISA 扩展说明。
9. `report/typst/formal-report.typ`、`report/typst/presentation.typ`：报告与演示的可维护源码。

当前主线一句话：

```text
ONNX -> IREE/MLIR carriers -> logical/physical CIM IR
     -> native linking -> CimExecutable -> final ISA / runtime
```

第二层材料按用途分开：

- [iree-study/README.md](iree-study/README.md)：IREE 全流程、Codegen/HAL 机制与 CIM 后端适配；
- `reference/**`：外部compiler、scheduler和CIM硬件方案阅读。

[实现问答](interview-prep/README.md)按“为什么分阶段、权重复制怎样实现、SRAM 怎样复用”的顺序展开。

报告和演示分别导出到 [正式报告 PDF](../output/pdf/cim-compiler-design-formal.pdf) 与
[答辩演示 PDF](../output/pdf/cim-compiler-presentation.pdf)。图源为 `report/assets/*.drawio`，
Markdown 使用同目录 SVG，Typst 使用 `report/typst/assets/*.pdf`。修改图源后同步导出 SVG，
再在仓库根目录执行 `conda run -n npu python doc/report/typst/build.py` 重建图 PDF 与两份文档。
