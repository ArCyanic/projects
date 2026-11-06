# 0　输入预处理：统一线性计算

赛题模型以 ONNX 提供，其中的线性层主要由 `MatMulInteger` 和 `Gemm` 表达。权重张量采用 `[N,K]` 布局；输入预处理在 ONNX 已导入 Torch MLIR、IREE 开始通用输入转换之前运行，将合同内的整数线性层统一为原生 Linalg 张量计算。

## 用 indexing map 表达权重方向

对激活 `[M,K]` 和权重 `[N,K]`，矩阵乘的三个访问映射为：

```mlir
#activation = affine_map<(m, n, k) -> (m, k)>
#weight = affine_map<(m, n, k) -> (n, k)>
#result = affine_map<(m, n, k) -> (m, n)>
```

`linalg.matmul` 直接使用这些原生 `indexing_maps`。转置由索引关系表达，预处理无需先构造 ONNX Transpose；后续静态权重读取按照 contraction 的 K/N 维提取 `[K,N]` 矩形。

## 共用整数矩阵乘

signed i8/i32 激活与 signed i8 权重通过同一个过程下降：

```text
Torch value tensors
  → torch_c.to_builtin_tensor
  → i32 zero init + linalg.matmul
  → torch_c.from_builtin_tensor
  → ONNX Add                    # 存在 bias 时
```

`torch_c` materialization 只负责类型桥接。Matmul 的原生 `cast_signed` 语义在乘加前完成符号扩展，结果使用 i32；因此无需先将全部权重转成 i32，也无需修改 Torch `aten.mm` 的同类型约束。

显式 `transB` 的 i8 Gemm 保持由上游转换处理。带额外 zero-point operands 的 MatMulInteger 也交给上游，预处理不会忽略这些操作数。这里没有扩展 unsigned、非默认 alpha/beta/transA 的硬件执行合同。

## 交给全局优化的程序

预处理输出仍是普通 tensor/linalg/arith 计算，线性层具有明确的 K/N 关系和整数结果类型。偏置保留为矩阵乘后的数据依赖。i32×i8 直接生成 i32 结果；原生 i8 Matmul 也采用 i32 accumulator，后续无需额外的截断规范化 pass。全局优化沿完整张量图寻找能够合并的分支。
