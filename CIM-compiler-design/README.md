# CIM Compiler Design

面向 2026 知存科技杯存算一体编译器架构任务的 CIM compiler 原型。

```text
ONNX
  -> iree-import-onnx Torch/ONNX MLIR
  -> IREE input: CIM linear normalization + native input conversion
  -> IREE preprocessing: optional heterogeneous fusion
                         + native horizontal contraction fusion
  -> IREE global-optimization: native tensor optimizations
  -> IREE dispatch-creation: native dispatch region formation
  -> IREE Flow / Stream / HAL carriers
  -> bufferization / memref carriers
  -> executable-targets linkable CIM target IR
  -> CIM backend linking
     -> executable merge / logical optimization / static Array placement
     -> one module initializer / SRAM physicalization
  -> hal.executable.binary(format = "cim-executable", data = CimExecutable)
  -> IREE local runtime numeric execution
     + optional .cim.payload / .cim.isa dumps
```

CIM 在 executable-targets 生成逻辑目标程序，在 HAL linking 后完成权重重组、Array 规划与 SRAM 物理化。
同一份物理 IR 序列化为运行时 payload 与 `.cim.isa`；Python 入口负责调用原生工具和收集产物。

## 单阵列目标

比赛主线面向单个 CIM Array。Hardware profile 提供 SRAM 容量、对齐和阵列行列尺寸；
目标操作与 ISA 直接使用该阵列的坐标。

## 构建与复现

按本节从源码构建 CIM 插件、导出全部中间 IR、运行官方模型并跑数值 gate。阶段语义见
[`doc/pipeline.md`](doc/pipeline.md)。cmake 可选加速和工具路径覆盖见
[`doc/build-run-test.md`](doc/build-run-test.md)。

### 环境

需要 Python 3.14、CMake、Ninja、支持 C++17 的编译器。用任意虚拟环境即可，版本以
`requirements.txt` 为准。首次克隆后：

```bash
git submodule update --init iree
git -C iree submodule update --init
python3 -m pip install -r requirements.txt
```

`requirements.txt` 提供 `iree-import-onnx`（来自 `iree-base-compiler`）以及 pytest /
ONNX Runtime。后续命令都在该 Python 环境、仓库根目录下执行。
`tools/cim-compile` 默认调用 `iree-build/tools/iree-compile`；可用环境变量
`CIM_IREE_COMPILE` 和 `CIM_IREE_IMPORT_ONNX` 覆盖。

### 编译 IREE 与 CIM 插件

```bash
cmake -S iree -B iree-build -G Ninja -C cmake/cim.cmake
cmake --build iree-build --target iree-compile iree-run-module iree-opt -j8
```

[`cmake/cim.cmake`](cmake/cim.cmake) 使用 CMake 原生初始缓存机制，集中维护 CIM 构建默认值。
`-D` 可覆盖具体选项，已有构建目录沿用其缓存；不同 build type 建议使用独立目录。
构建完成后：

```bash
iree-build/tools/iree-run-module --list_drivers
```

应列出 `cim`。

### 导出全部中间 IR

一条命令、一次编译即可保留 IREE 的 12 个 phase 和 CIM 链接后物理化的各阶段：

```bash
python3 tools/cim-compile onnx/int8_linear_add.onnx \
  --emit-dir output/cim-int8-linear-add --emit-stages
```

`--emit-stages` 只允许完整的 `payload`（默认）或 `vmfb` 编译。产出：

```text
output/cim-int8-linear-add/
  int8_linear_add.onnx_torch.mlir     iree-import-onnx 结果
  int8_linear_add.cim.payload         运行时二进制
  int8_linear_add.cim.isa             同一物理程序的文本投影
  stages/iree/                       12 个 IREE phase
  stages/cim/                        链接后物理化各阶段（只写出 CIM 目标 executable）
```

IREE dump 文件名把导入 MLIR 路径中的 `.` 换成 `_`，例如
`int8_linear_add_onnx_torch.1.input.mlir`。CIM dump 是 `N.label.mlir`。
下表对应默认 `--optimization-pipeline=replicated`（`--sram-allocation=reuse`）；
若改成 `direct`，会跳过 packed/replicated dump，后续序号前移。

| 文件 | 在 `int8_linear_add` 上看到什么 |
| --- | --- |
| `*.1.input.mlir` | 规范化后的 `linalg.matmul`（`8x256xi8 × 256x128xi8`） |
| `*.5.dispatch-creation.mlir` | `flow.dispatch.workgroups` 边界 |
| `*.10.executable-targets.mlir` | 单个 executable 内的逻辑 `cim.mvm` / `cim.elt` |
| `*.11.hal.mlir` | `hal.executable.binary`，`format = "cim-executable"` |
| `1.linked.mlir` | 链接后、排布前：4 个 `cim.mvm`（同一 GEMM 的 4 个连续激活行） |
| `2.packed.mlir` | 本模型没有可横向拼接的独立 GEMM，仍为 4 个 `cim.mvm` |
| `3.replicated.mlir` | 权重复制后 1 个 `cim.mvm` |
| `6.bit-serial.mlir` | `cim.mvm` 换成 8 个 `cim.bit`，部署入口保留 `cim.array.load` |
| `7.sram-allocated.mlir` | 多个 `memref.alloc` 收成一块 SRAM arena 加 `memref.view` |
| `8.physical.mlir` | 带 SRAM / Array 坐标的最终物理程序 |
| `int8_linear_add.cim.isa` | `.deployment @__cim_array_init` 之后是 `.runtime` 计算程序 |

横向 packing 在 `onnx/resource_showcase.onnx` 上更清楚：同样加 `--emit-stages` 后，
`1.linked.mlir` 有 16 个 `cim.mvm`，`2.packed.mlir` 变成 4 个。

只停在某一个 IREE 阶段时用 `--compile-to`，不生成 `stages/`：

```bash
python3 tools/cim-compile onnx/int8_linear_add.onnx \
  --emit-dir output/cim-pre --compile-to preprocessing
```

得到 `int8_linear_add.iree_linalg.mlir`。可选停点：`preprocessing`、`flow`、`stream`、
`executable-configurations`、`executable-targets`、`hal`、`payload`、`vmfb`。

### 运行

```bash
python3 tools/cim-compile onnx/int8_linear_model.onnx \
  --emit-dir output/cim-int8-linear --compile-to vmfb

iree-build/tools/iree-run-module \
  --module=output/cim-int8-linear/int8_linear_model.vmfb \
  --device=cim \
  --function=int8_linear_graph \
  --input=32x512xi8=0 \
  --output=-
```

官方五个模型的入口与输入形状：

| ONNX | `--function` | `--input` |
| --- | --- | --- |
| `int8_linear_model.onnx` | `int8_linear_graph` | `32x512xi8` |
| `int8_linear_add.onnx` | `int8_linear_add_very_large_graph` | `8x256xi8`，`8x128xi32` |
| `four_operator_sequential.onnx` | `four_operator_int8_graph` | `8x256xi8`，`8x128xi32`，`8x64xi32` |
| `residual_four_op.onnx` | `residual_graph` | `8x256xi8`，`8x128xi32` |
| `three_branch_four_op.onnx` | `three_branch_graph` | `4x192xi8`，`4x96xi32`，`4x96xi32` |

### 测试

```bash
python3 -m pytest -q
```

测试覆盖五个官方模型和六个 showcase 的 VMFB/ONNX Runtime bit-exact 比较、消融检查，
以及算术语义、静态权重、视图地址和 SRAM 覆盖证明的回归。测试在临时目录生成 ORT 兼容的
规范化 ONNX；`.cim.isa` 是同源展示投影。用 `python3 -m pytest --collect-only -q` 查看当前测试清单。

### 优化消融

```bash
python3 tools/cim-showcase --output-dir output/cim-showcase
```

工具读取同一次编译生成的 `.cim.isa` 和 `.cim.payload`，按边打印 deployment 占用和
per-workgroup 的 MVM / bit round / SRAM 指标。数字以这次执行为准；指标含义见
[`doc/experiments/optimization-ablation-report.md`](doc/experiments/optimization-ablation-report.md)。

## ONNX Frontend

主线入口是 `tools/cim-compile`。官方 ONNX 是唯一 source，直接由
`iree-import-onnx` 生成 Torch/ONNX MLIR；CIM 插件随后在 IREE input conversion
之前规范化 linear op。编译流程不修改、复制或生成 ONNX。

MLIR normalization 只补 IREE/ONNX lowering 需要的显式 linear 结构：

- signed i8/i32 activation 与 signed i8 权重共用原生 `torch_c` tensor materialization
  和 `linalg.matmul`，以 i32 累加，保留权重位宽；
- `[out, in]` RHS 由 Matmul 的 `indexing_maps` 表达转置，不再构造 ONNX Transpose；
- 可选 bias 继续交给原生 ONNX Add 转换；显式 zero-point 的 MatMulInteger 留给上游转换。

## 关键文档

活动入口：

- `doc/README.md`：文档入口。
- `doc/guide/README.md`：按 IREE 接入阶段组织的完整学习主线。
- `doc/architecture.md`：单阵列编译器的全局设计。
- `doc/build-run-test.md`：cmake 可选加速和 `CIM_IREE_*` 工具路径覆盖。
- `doc/pipeline.md`：lowering graph、stage order、carrier checkpoints、compact payload 和 final `.cim.isa` projection。
- `doc/spec/README.md`：SPEC 索引。
- `doc/spec/isa/cim-isa-spec.md`：final ISA grammar与physical-program projection。
- `doc/spec/runtime-abi-spec.md`：`cim-executable` numeric runtime ABI。
- `doc/spec/cim-executable-payload-spec.md`：`CimExecutable` payload contract。
- `doc/experiments/optimization-ablation-report.md`：四项单变量消融和组合Case的可复现实验报告。

`doc/archive/**` 保存比赛原始材料。
