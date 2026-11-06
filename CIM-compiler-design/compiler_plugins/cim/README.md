# CIM IREE Plugin

本目录包含tracked CIM compiler plugin和runtime registration。Compiler侧注册`cim` dialect与HAL target backend；
runtime侧把当前CIM executable loader通过external factory接入stock IREE local-sync。
当前主线让 executable-targets 生成 linkable logical CIM target IR；CIM backend linking
完成固定logical优化、全deployment静态weight placement、唯一Array initializer和SRAM physicalization；
serialization最后从同一linked physical IR投影`cim-executable` payload与final ISA。推理期间compute
exports不含Array Load。

矩阵乘采用 signed i8/i32 activation × signed i8 静态权重。权重支持原生 Dense 与
DenseResource 常量；运行时传入的权重不属于静态部署合同。Contraction 的索引映射、
`cast` 属性和标量 region 必须共同满足这项语义。自有 contest Gemm 规范化要求
`transA=0, alpha=1, beta=1`；显式 `transB=1` 的 i8 Gemm 继续使用已验证的上游转换。

当前 active 文档入口：

- `doc/pipeline.md`
- `doc/spec/cim-dialect-surface-spec.md`

生产产物是：

```text
hal.executable.binary(format = "cim-executable", data = CimExecutable)
```

`.cim.isa` 用于阅读物理程序；Runtime 执行 `CimExecutable` payload。

## 构建入口

构建、运行、中间 IR 和测试命令维护在仓库根目录 `README.md`。插件经 `IREE_CMAKE_PLUGIN_PATHS`
静态注册，使用原生 input conversion 和 preprocessing 扩展点；
Flow 与 Stream 不插入自定义 pass。HAL target/backend hooks 接管 executable 翻译与链接后物理化。

构建按实际交付单位划分：compiler 只有一个 `registration` 库，显式列出全部 C++ 实现与
直接依赖；`Frontend/IR/Common/Codegen/Target` 保留为源码职责目录。两份 `.td` 输入分别由
原生 TableGen target 生成，其依赖直接挂在 compiler target 上。Runtime 使用独立的
`cim_runtime::driver` target，支持 `IREE_BUILD_COMPILER=OFF` 的构建。
