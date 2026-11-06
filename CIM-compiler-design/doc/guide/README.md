# CIM 编译流程

这套文档沿一个 ONNX 整数线性计算的下降过程，解释它如何成为单阵列上的物理程序。章节编号对应 CIM 在 IREE 中实际介入的先后顺序；`4.x` 和 `5.x` 分别展开目标翻译与链接后物理化，因为主要算法集中在这两个阶段。

建议从第 0 章顺序阅读。每一章都以上一阶段的程序为输入，说明当前可见的信息、发生的变换以及交给下一阶段的结果。

```text
ONNX
  → 0 输入预处理
  → 1 全局图优化
  → 2 Dispatch 形成
  → 3 目标配置
  → 4 目标翻译
       → 4.1 二维合法化
       → 4.2 逻辑 CIM IR
  → 5 链接后物理化
       → 5.1 权重排布
       → 5.2 单阵列放置
       → 5.3 位串行与 SRAM
       → 5.4 可执行程序
  → 6 Runtime 执行
```

## 阅读顺序

| 章节 | 程序在这一阶段获得什么 |
| --- | --- |
| [0　输入预处理](0-input-preprocessing.md) | 统一的整数线性计算形态 |
| [1　全局图优化](1-global-optimization.md) | 可跨分支合并的块对角计算 |
| [2　Dispatch 形成](2-dispatch-creation.md) | 共享输入计算的共同任务边界 |
| [3　目标配置](3-target-configuration.md) | workgroup 与阵列 tile 策略 |
| [4　目标翻译](4-target-translation.md) | 从张量任务到可链接目标程序的完整路径 |
| [4.1　K/N 二维合法化](4.1-array-legalization.md) | 阵列尺寸合法的计算窗口和结果恢复关系 |
| [4.2　逻辑 CIM IR](4.2-logical-cim-ir.md) | 可继续重排权重的 `cim.mvm`/`cim.elt` 程序 |
| [5　链接后物理化](5-linked-physicalization.md) | 面向整个部署的统一物理化顺序 |
| [5.1　权重排布](5.1-weight-layout.md) | 更少的 MVM 窗口及其阵列空间代价 |
| [5.2　单阵列放置](5.2-static-array-planning.md) | 唯一阵列中的常驻矩形和部署入口 |
| [5.3　位串行与 SRAM](5.3-bit-serial-and-sram.md) | 物理计算轮次、临时对象和固定 SRAM 地址 |
| [5.4　可执行程序](5.4-executable-program.md) | payload 与 ISA 的同源物理程序 |
| [6　Runtime 执行](6-runtime-execution.md) | 权重部署、workgroup SRAM 和数值执行 |

本教程解释设计与变换过程。[IREE 接入阶段](../pipeline.md) 维护精确的阶段顺序，[规范索引](../spec/README.md) 维护 IR、payload、ISA 和 Runtime ABI 的字段级契约，仓库根目录 [README](../../README.md) 维护构建、中间 IR 与测试命令。
