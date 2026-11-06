# 构建、运行、测试 Runbook

本文不重复阶段语义；阶段顺序与 contract 见 `doc/pipeline.md` 和 `doc/spec/**`。

## 环境

构建需要 Python 3.14、CMake、Ninja 和支持 C++17 的编译器。首次克隆后初始化 IREE 子模块，并在
任意 Python 3.14 环境中安装依赖：

```bash
git submodule update --init iree
git -C iree submodule update --init
python3 -m pip install -r requirements.txt
```

`requirements.txt` 固定 ONNX 导入、实验与数值验证直接使用的 Python 库版本，其中
`iree-base-compiler` 提供 `iree-import-onnx`。后续命令均在该环境、仓库根目录下执行。
编译工具默认来自 `iree-build/tools/`；可分别用 `CIM_IREE_COMPILE` 和
`CIM_IREE_IMPORT_ONNX` 覆盖。

## 构建

构建配置集中在 [`cmake/cim.cmake`](../cmake/cim.cmake)。在仓库根目录执行：

```bash
cmake -S iree -B iree-build -G Ninja -C cmake/cim.cmake
cmake --build iree-build --target iree-compile iree-run-module iree-opt -j8
```

这是 CMake 原生 `-C` 初始缓存文件，为新构建目录提供 Release 与 CIM 默认配置；已有缓存
继续生效，显式 `-D` 可覆盖选项。插件、TableGen 和 runtime 均由 IREE 原生 CMake 规则构建。

本机若已安装 ccache，可使用标准 compiler launcher：

```bash
cmake -S iree -B iree-build -G Ninja -C cmake/cim.cmake \
  -DCMAKE_C_COMPILER_LAUNCHER=ccache \
  -DCMAKE_CXX_COMPILER_LAUNCHER=ccache
```

默认配置启用 CIM 插件和 local-sync，关闭上游测试、样例、TFLite bindings、额外输入方言
及默认 CPU/GPU backend。常量求值等编译器内部路径所需的组件继续由 IREE 自动配置。
不同 build type 建议使用独立目录，通过 `CIM_IREE_COMPILE` 指向相应编译器。

## 编译阶段与中间结果

`tools/cim-compile` 的 `--compile-to` 停点和 `--emit-stages` 目录布局见仓库 README。
默认 `--optimization-pipeline=replicated` 时，CIM dump 文件名为：

```text
1.linked.mlir  2.packed.mlir  3.replicated.mlir  4.array-planned.mlir
5.sram-materialized.mlir  6.bit-serial.mlir  7.sram-allocated.mlir  8.physical.mlir
```

`direct` 会跳过 packed/replicated dump，后续序号前移。IREE 的 12 个 phase 由
`--dump-compilation-phases-to` 生成，文件名形如
`<imported-mlir-stem>.N.phase.mlir`。

优化消融：

```bash
python3 tools/cim-showcase --output-dir output/cim-showcase
```

打印结果以当前执行为准。完整表、成本解释和复现步骤见
`doc/experiments/optimization-ablation-report.md`。
