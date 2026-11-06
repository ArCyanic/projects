# CIM Executable Configuration Design

目标配置为每个 dispatch 选择两级 tile 与 translation pipeline。阶段顺序见 [编译管线](../pipeline.md)。
Executable-targets 阶段设计见
[`cim-executable-targets.md`](cim-executable-targets.md)。

## Design Goal

`executable-configuration` 是 CIM target lowering 前的 strategy handoff。它的职责是把
IREE common preprocessing 后的 dispatch function 和 root op 标记为后续 target lowering
需要的策略事实。

当前主线保持 IREE 原生分层：

```text
dispatch function + supported linalg root
  -> root lowering_config = #iree_codegen.lowering_config<...>
  -> function translation_info.passPipeline = #iree_codegen.pass_pipeline<"cim-workgroup">
  -> executable-targets consumes lowering_config + selected pipeline
```

这个阶段只建立 target lowering 所需的正统 strategy carriers：root-local
`lowering_config` 和 function-level `translation_info`。它不建立 SRAM plan、weight
placement、physical workgroup order 或 payload facts。

## Carrier Model

`translation_info.passPipeline` 选择 CIM executable-targets pipeline：

```text
#iree_codegen.translation_info<
  pipeline = #iree_codegen.pass_pipeline<"cim-workgroup">
>
```

IREE 原生 `PassPipelineAttr` 已实现 `PipelineAttrInterface`，通过 MLIR pipeline registry 解析
`cim-workgroup` 并构造 executable-targets lowering pipeline。CIM 只注册这条 named pipeline，
无需自定义 pipeline attr、枚举或全局函数指针回调。

Root `lowering_config` 承载具体 tile decision，属性名和 attr 类型都使用 IREE 原生
`#iree_codegen.lowering_config`：

```text
#iree_codegen.lowering_config<tile_sizes = [
  [...],  // workgroup
  [...]   // Array tile inside entry
]>
```

- `workgroup`：按 root op loop space表达 inter-workgroup M/batch tile；N=0。
- `Array`：按 root op loop space表达 single-workgroup内部 M/N/K tile。
- 不属于该 level 的 loop dimension 用 `0`。
- 对 matmul loop `[m, n, k]`，形态为
  `workgroup = [MTile, 0, 0]`、`Array = [1, NTile, KTile]`。

硬件 profile 不进入 `translation_info.configuration`。进入 executable variant 后，硬件事实由
`ExecutableTargetAttr.configuration["profile"]` 提供。configuration 读取该 profile 来计算
root lowering_config；后续 scheduler、serializer 和 payload header 仍从同一个 resolved
profile 读取。Profile 是 lowering_config 的输入，不是 lowering_config 的内容。

## Pipeline Shape

CIM configuration pipeline 复用 IREE common codegen preprocessing，然后运行一个薄 selector：

```text
buildConfigurationPassPipeline(targetAttr, passManager)
  buildCodegenConfigurationPreProcessingPassPipeline(passManager)
  buildCIMCodegenConfigurationPassPipeline(passManager.nest<ModuleOp>())

buildCIMCodegenConfigurationPassPipeline(modulePM)
  FunctionLikeNest(modulePM).addCommonTargetExecutablePreprocessingPasses()
  modulePM.addPass(MaterializeUserConfigsPass)
  FunctionLikeNest(modulePM)
    .addPass(MaterializeDeviceEncodingPass)
  modulePM.addPass(CIMSelectLoweringStrategyPass)
```

Dispatch tensor boundary 在本阶段保持 TensorExt 形态。Tiling 后的
`BufferizeDispatchTensorLoadStorePass` 和 comprehensive bufferization 属于
`executable-targets`；configuration 不为 selector 提前改变 boundary IR。

## Selector Behavior

`CIMSelectLoweringStrategyPass` 遍历 inner module 中的 `FunctionOpInterface`：

```text
for each supported linear root without existing user configuration:
  compute final CIM workgroup/Array tile sizes from root shape + profile
  set root lowering_config = #iree_codegen.lowering_config<...>

for each dispatch function with configured CIM root:
  set translation_info.passPipeline = #iree_codegen.pass_pipeline<"cim-workgroup">
```

Selector 从 function 内的 contraction root 计算 tile。

Existing IREE user configuration is authoritative：如果`MaterializeUserConfigs`已经写入`translation_info`，
selector不再解释或修复它。

唯一默认策略是：对前三个索引映射做 `inferContractionDims` 得到 M/N/K 循环下标（`isaContractionOpInterface`
与横向融合 contraction 同一条路径），再按这些下标写入两级 tile：

```text
KTile = largest uniform divisor of K not exceeding array_rows
NTile = largest uniform divisor of N not exceeding
        array_columns / weight_bits
MTile = largest divisor of M not exceeding
        min(array_rows / KTile,
            array_columns / weight_bits / NTile)

workgroup[m] = MTile
array[m] = 1
array[n] = NTile
array[k] = KTile
```

该`MTile=B`形成可复用的最小B-row program，`M/B`个workgroup覆盖完整M。`isaContractionOpInterface` 与横向融合
contraction 共用这一套 M tile。Replication pass只识别该program内的连续activation rows，不跨
workgroup展开rows。Physical N split与二维placement由Array planner对linked variant的全部weights
统一完成。

该策略不读取其他executables，也不需要configuration后的top-level pass或分段compiler invocation。

## Code Ownership

阶段代码保持四个直接 owner：

| File | Role |
| --- | --- |
| `compiler_plugins/cim/src/PluginRegistration.cpp` | 在 IREE plugin global pass registration seam 注册 CIM passes 与 MLIR named pipeline。 |
| `compiler_plugins/cim/src/cim/Codegen/CIMPasses.td` | 当前 CIM passes 的 MLIR generated interface。 |
| `compiler_plugins/cim/src/cim/Codegen/CIMPasses.h/.cpp` | 对外只暴露 stage pipeline builders；内部组合 IREE common preprocessing、CIM selector 与 generated pass registration。 |
| `compiler_plugins/cim/src/cim/Codegen/CIMSelectLoweringStrategyPass.cpp` | select root IREE native `lowering_config` and function `translation_info`。 |

MVM geometry、dtype、RHS source、weight layout、`i32 x i8 -> i32` 语义和 rewrite action
继续由 executable-targets lowering 拥有。

## Handoff

离开本阶段后，CIM 后续阶段只依赖三个稳定事实：

```text
root lowering_config
  carries final two-level workgroup/Array tile sizes.

translation_info.passPipeline
  selects #iree_codegen.pass_pipeline<"cim-workgroup">.

ExecutableTargetAttr.configuration["profile"]
  selects the effective hardware profile.
```

后续阶段不再修改`lowering_config`。具体translation形态见
[`cim-executable-targets.md`](cim-executable-targets.md)：它用 IREE-style selected-pipeline
runner 运行 `#iree_codegen.pass_pipeline<"cim-workgroup">`，并形成后续 HAL/linking 消费的稳定 target IR。
