# 4　目标翻译：从 Dispatch 到逻辑 CIM 程序

目标翻译消费上一阶段记录的两级 tile，把 dispatch 中的张量计算变成可链接的 CIM 目标程序。变换从外到内推进：先建立 workgroup 边界，再把每个矩阵乘分成阵列可执行窗口，最后把张量缓冲化并转换为逻辑 CIM 操作。

```text
configured dispatch
  → M 维 workgroup 分块
  → K/N 阵列分块与结果恢复
  → 横向融合 contraction 分解
  → dispatch 边界缓冲化
  → tensor/linalg 转为 memref 与逻辑 CIM IR
  → 可链接的 target executable
```

M 维 workgroup 分块保留参数化执行。生成的视图地址仍依赖 workgroup 坐标，IREE 后续在 dispatch 时提供具体的 `(x,y,z)`。K/N 分块发生在每个 workgroup 内部，它决定逻辑 MVM 的矩形形状。

缓冲化把张量切片变成 `memref` 视图。静态权重由目标局部的只读全局数据承载，dispatch 输入输出保持 HAL 接口关系，内部结果成为普通缓冲区。逻辑 CIM 转换随后识别矩阵乘和整数逐元素计算，生成 `cim.mvm` 与 `cim.elt`。

阶段结束时，每个 MVM 都满足阵列单次计算的 K/N 尺寸，但权重还没有最终坐标，动态缓冲区也没有 SRAM 偏移。这样的目标程序可以被 IREE 链接，并在链接后继续执行面向整个部署的优化。
