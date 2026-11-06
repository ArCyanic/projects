# IREE VM Pipeline 阶段功能划分

本文只记录 IREE 官方源码中 `compiler/src/iree/compiler/Pipelines/Pipelines.h`
暴露的 VM transformation pipeline 阶段。内容按本地 IREE 源码调研整理，不讨论任何外部工程如何使用这些阶段。

## 入口与阶段枚举

| 条目 | 代码位置 | 作用 |
| --- | --- | --- |
| 阶段枚举 | `iree/compiler/src/iree/compiler/Pipelines/Pipelines.h` | `IREEVMPipelinePhase` 定义 `start` 到 `end` 的阶段顺序。 |
| 阶段名与说明 | `iree/compiler/src/iree/compiler/Pipelines/Pipelines.h` | `enumerateIREEVMPipelinePhases` 给每个阶段绑定 CLI 可见名称和说明。 |
| 预编译 pipeline | `iree/compiler/src/iree/compiler/Pipelines/Pipelines.h`、`iree/compiler/src/iree/compiler/Pipelines/Pipelines.cpp` | `buildIREEPrecompileTransformPassPipeline` 覆盖 `input` 到 `global-optimization`。 |
| 完整 VM pipeline | `iree/compiler/src/iree/compiler/Pipelines/Pipelines.h`、`iree/compiler/src/iree/compiler/Pipelines/Pipelines.cpp` | `buildIREEVMTransformPassPipeline` 先调用预编译 pipeline，再继续到 `vm`/`end`。 |
| 默认 pipeline | `iree/compiler/src/iree/compiler/Pipelines/Pipelines.cpp` | `buildDefaultIREEVMTransformPassPipeline` 从命令行 flags 取 options，并因为默认入口没有 JIT hook 而关闭 const eval。 |
| pipeline 注册 | `iree/compiler/src/iree/compiler/Pipelines/Pipelines.cpp` | 注册名为 `iree-transformation-pipeline` 的完整 input-to-VM pipeline。 |
| 全局注册顺序 | `iree/compiler/src/iree/compiler/Tools/init_iree_passes.h` | IREE pass 初始化中先注册 HAL、HAL Inline、HAL Loader，再注册 VM passes，最后注册总 VM transformation pipeline。 |
| HAL 阶段映射 | `iree/compiler/src/iree/compiler/Pipelines/Pipelines.cpp`、`iree/compiler/src/iree/compiler/Pipelines/Pipelines.cpp` | VM pipeline 的 `executable-*` 阶段映射到 HAL pipeline 的 `PipelinePhase`。 |

## 总览表

| 顺序 | 阶段名 | 主入口 | 主要输入形态 | 主要输出形态 | 功能边界 |
| --- | --- | --- | --- | --- | --- |
| 0 | `start` | 无独立 pass；是 `compileFrom` 默认值 | 输入 MLIR module | 原始输入 module | 只表示 pipeline 入口，不添加 pass。 |
| 1 | `input` | `buildIREEPrecompileTransformPassPipeline` | 前端或插件输入 dialect、MLIR module | IREE 可接受的核心输入 dialect，常见为 linalg/tensor/arith/util/flow 辅助形式 | 自动或显式选择 input conversion，并运行公共输入清理、类型升降级。 |
| 2 | `abi` | `IREE::ABI::buildTransformPassPipeline`，可选 `IREE::TFLite::buildTransformPassPipeline` | 已合法化的 public entry functions | 带 IREE native ABI 或 TFLite 兼容 wrapper 的入口 | 根据执行模型选择 sync/coarse-fence 调用 ABI，包装 entry points，并做 inlining/canonicalize/CSE/SymbolDCE。 |
| 3 | `preprocessing` | `Preprocessing::buildPreprocessingPassPipeline` | ABI 后的核心输入 IR | 用户、Transform dialect、PDL、插件或属性驱动预处理后的 IR | 只执行显式/扩展预处理，不承担 IREE 主优化。 |
| 4 | `global-optimization` | `GlobalOptimization::buildGlobalOptimizationPassPipeline` | 仍以 tensor/linalg/flow/util 为主的全程序 IR | 全局规范化、常量/参数处理、形状与数值优化后的 IR | 在 dispatch 形成前做跨函数、跨全局的高层优化。 |
| 5 | `dispatch-creation` | `DispatchCreation::buildDispatchCreationPassPipeline` | 全局优化后的 tensor/linalg/flow 候选计算 | `flow.dispatch.region`/`flow.dispatch.workgroups` 及 flow tensor 边界 | 做融合预处理、形成 dispatch region/workgroup，物化 workgroup count。 |
| 6 | `flow` | `IREE::Flow::buildFlowTransformPassPipeline` | Flow dispatch region/workgroup IR | `flow.executable`、outlined dispatches、去重后的 Flow module | 验证 Flow 输入，outline dispatches，生成 executable 边界并清理全局/常量。 |
| 7 | `stream` | `IREE::Stream::buildStreamTransformPassPipeline` | Flow executable 和 dispatch 操作 | `stream.tensor` -> `stream.async` -> `stream.cmd` 资源/时间线 IR | 将 tensor-level dispatch 调度成 stream resource、async、cmd、timepoint 和 allocation 模型。 |
| 8 | `executable-sources` | `IREE::HAL::buildHALTransformPassPipeline` 的 HAL `ExecutableSources` | Stream IR 与 `stream.executable` | 带 target devices、HAL interfaces、未配置或预处理后的 `hal.executable` source | HAL 设备分配、接口物化、executable source dump/substitution/preprocess；尚未选择具体 translation strategy。 |
| 9 | `executable-configurations` | HAL `ExecutableConfigurations` | `hal.executable.variant` source IR | 已配置 target translation strategy 的 executable variants | 调用目标后端 configuration pipeline，给 variant/export 标注翻译策略和目标约束；尚未翻译成目标 IR/object。 |
| 10 | `executable-targets` | HAL `ExecutableTargets` | 已配置 executable variants | 已经过目标后端 translation 的 executable variants | 调用目标后端 translation pipeline；此后 executable body 可变成 SPIR-V、LLVM dialect 或其他目标形式。 |
| 11 | `hal` | HAL full transform tail | Stream/hal executable 混合 IR 与已翻译 executable | HAL dialect host program，必要时序列化 executable | 将 host program 转成 HAL，链接/序列化 executable，物化 runtime cache、device selection、resource 管理等。 |
| 12 | `vm` | `IREE::VM::buildVMTransformPassPipeline` | HAL/util/func/scf/cf 等 host-side IR | VM dialect module | 内联、控制流/affine 降低、std/util/HAL 等转换到 VM，整理 rodata、initializer、yield/discard。 |
| 13 | `end` | 无独立 pass；完整 pipeline 终点 | VM dialect module | 完整 pipeline 输出 | 表示 `compileTo = End` 不提前返回。 |

## 阶段详细表

| 阶段 | 代码路径 | 关键 pass / 子 pipeline | 精确功能划分 |
| --- | --- | --- | --- |
| `start` | `Pipelines.h:25`、`Pipelines.cpp:306` | 无 | 作为 `compileFrom` 默认值参与 `<` 比较，使后续阶段按枚举顺序加入 pass；自身不对应 `PassManager::addPass`。 |
| `input` | `Pipelines.cpp:111` | `InputConversion::createAutoInputConversionPipelinePass`、插件 `extendCustomInputConversionPassPipeline`、`InputConversion::buildCommonInputConversionPassPipeline` | `inputType=none` 时不跑专用转换；`auto` 时根据 module 内容选择插件；其他 mnemonic 交给插件。公共 pipeline 运行 `createIREEImportPublicPass`、`createImportMLProgramPass`、`createSanitizeModuleNamesPass`，并按 options 做 f64/f32/f16/bf16/i64 类型升降级。 |
| `abi` | `Pipelines.cpp:164` | Native ABI: `createConvertStreamableOpsPass`、`createWrapEntryPointsPass`、inliner、canonicalizer、CSE、SymbolDCE；TFLite: `createWrapEntryPointsPass`、cleanup | Native ABI 根据 `SchedulingOptions::ExecutionModel` 选择 `Sync` 或 `CoarseFences` invocation model。该阶段只处理入口 ABI 和 binding wrapper，不做 dispatch 切分。 |
| `preprocessing` | `Pipelines.cpp:254`、`Preprocessing/Passes.cpp:97` | 命令行 textual pass pipeline、Transform dialect interpreter、PDL patterns、plugin extension、`createAttrBasedPipelinePass` | 预处理优先级为：显式 pass pipeline、Transform spec、PDL spec、插件扩展、函数属性 `preprocessing_pipeline`。IREE 还注册了几个可单独调用的 preprocessing pipeline，如 transpose convolution、backward-data conv、make single dispatch。 |
| `global-optimization` | `Pipelines.cpp:269`、`GlobalOptimization/Passes.cpp:99` | 参数 import/export/splat、warn/strip debug、int arithmetic、quantized conv/matmul canonicalization、elementwise-to-linalg、shape expansion、transpose propagation、data tiling、constant hoisting、const eval hook、numeric narrowing | 该阶段仍在 dispatch 形成前，主要目标是让 tensor/linalg/flow/util IR 达到有利于融合和 dispatch 形成的全局规范形态。`constEval` 需要外部 hook；默认 pipeline 因没有 JIT hook 在 `buildDefaultIREEVMTransformPassPipeline` 中关闭。 |
| `dispatch-creation` | `Pipelines.cpp:387`、`DispatchCreation/Passes.cpp:334` | tensor tracing、pad lowering、fixed-point IPO cleanup、fusion preprocessing、dispatch region preprocessing/creation、`createConvertDispatchRegionsToWorkgroupsPass`、`createConvertTensorToFlowPass`、`createMaterializeDefaultWorkgroupCountRegionPass`、unsupported element bitcast | 该阶段把可融合 tensor/linalg 计算收束到 Flow dispatch/workgroup 边界。输出的关键形态是 Flow dispatch workgroups 以及显式 workgroup count region。 |
| `flow` | `Pipelines.cpp:402`、`Dialect/Flow/Transforms/Passes.cpp:123` | `createVerifyInputLegalityPass`、`createVerifyInitializationOrderPass`、`createAttributeCallGraphPass`、empty tensor init、dynamic dims capture、outline dispatch externs/regions、annotate/dedup executables、outline constants、IPO cleanup、SymbolDCE | Flow 阶段确认 dispatch-level 语义合法，outline dispatch region 到 executable，给 dispatch/executable 添加可供后续阶段使用的边界和注解，并对 executable/constant/global 做去重清理。 |
| `stream` | `Pipelines.cpp:416`、`Dialect/Stream/Transforms/Passes.cpp:474` | `buildStreamTensorPassPipeline`、`buildStreamAsyncPassPipeline`、`buildStreamCmdPassPipeline`、可选 statistics dump、`buildStreamOptimizationPassPipeline`、final cleanup/SymbolDCE | Stream 阶段是资源和时间线调度核心。它按层次把输入 lowering 到 `stream.tensor.*`，再到 `stream.async.*`，再到 `stream.cmd.*`，最后优化 allocation、timepoint、binding、dispatch operands。 |
| `executable-sources` | `Pipelines.cpp:432`、`HAL/Transforms/Passes.cpp:333` | `buildHALDeviceAssignmentPassPipeline`、`buildHALConfigurationPassPipeline`、`createPreprocessExecutablesPass` | VM phase 映射到 HAL `PipelinePhase::ExecutableSources`。完成目标设备分配、device promise/alias 解析、HAL interface materialization、executable pruning、source dump/substitution/capture，以及可选外部 executable preprocessing。 |
| `executable-configurations` | `Pipelines.cpp:432`、`HAL/Transforms/Passes.cpp:366` | nested `createConfigureExecutablesPass`、target backend `buildConfigurationPassPipeline`、configuration dump/capture/substitution、benchmark dump | VM phase 映射到 HAL `PipelinePhase::ExecutableConfigurations`。核心是按 executable target 调用目标后端配置 pipeline，选择并标注 translation strategy；还未执行目标代码生成。 |
| `executable-targets` | `Pipelines.cpp:432`、`HAL/Transforms/Passes.cpp:429` | nested `createTranslateAllExecutablesPass`、target backend `buildTranslationPassPipeline`、translated source capture | VM phase 映射到 HAL `PipelinePhase::ExecutableTargets`。该阶段执行目标后端 translation。HAL 注释明确此后 executable 变成 opaque blobs，接口不可再改。 |
| `hal` | `Pipelines.cpp:437`、`HAL/Transforms/Passes.cpp:468` | `createConvertToHALPass`、memoize region inline/outline、prune executables、`createLinkAllExecutablesPass`、hoist executable objects、resolve export ordinals、materialize resource caches、device memoization/query、command cleanup、initialize devices、affine/scf lowering、serialize executables、fixed-point IPO cleanup | 完成 host program 到 HAL dialect 的转换和 executable packaging。常规 async execution 走 `buildHALTransformPassPipeline`；`InlineStatic` 和 `InlineDynamic` 分别走 HAL Inline 与 Loader pipeline；`HostOnly` 不需要 HAL。 |
| `vm` | `Pipelines.cpp:470`、`Dialect/VM/Transforms/Passes.cpp:77` | inliner、SymbolDCE、verify init order、combine initializers、SCF/affine/control-flow cleanup、subrange propagation、VM conversion、rodata table reify/hoist/dedup/resolve、global initialization、function annotation、yieldable call conversion、stack-size optimization、drop barriers、materialize ref discards | 将 host-side IR 收敛到 VM dialect。`TargetOptions` 影响 index bits、float extensions、unsupported float truncation、stack size 优化等转换选项。 |
| `end` | `Pipelines.h:75`、`Pipelines.cpp:479` | 无 | `compileTo=End` 时不会在 `vm` 后提前返回；该阶段只是完整 pipeline 的终止点。 |

## Stream 子 pipeline

| 子 pipeline | 代码位置 | 输入 | 输出 | 核心动作 |
| --- | --- | --- | --- | --- |
| cleanup | `Dialect/Stream/Transforms/Passes.cpp:40` | 任意 Stream pipeline 中间 IR | 更规范的 util/func/stream IR | canonicalizer、CSE、int arithmetic、global access simplification、apply patterns、fold/fuse globals、IPO。 |
| tensor | `Dialect/Stream/Transforms/Passes.cpp:75` | Flow/stream 输入 | `stream.tensor.*` 为主 | verify input、cleanup、clone-to-consumers、可选 affinity annotation、`createConvertToStreamPass`、verify lowering-to-tensors、combine initializers、fixed-point cleanup、可选 global encoding unification。 |
| async | `Dialect/Stream/Transforms/Passes.cpp:178` | `stream.tensor.*` | `stream.async.*`、timepoints、execution regions | specialize/materialize encodings、host/device tensor encoding、layout slices、verify async resources、可选 split parameter encoder、copy-on-write、copy elision、allocation emplacement、usage refinement、async access verification、schedule execution/concurrency、sync initializers、propagate timepoints、materialize builtins、verify async lowering。 |
| cmd | `Dialect/Stream/Transforms/Passes.cpp:329` | `stream.async.*` | 显式 `stream.cmd.*` | schedule allocation、emplace transients、materialize transient size queries、pack constants、layout slices、propagate subranges、automatic reference counting、annotate constant transient size、verify cmd lowering。 |
| optimization | `Dialect/Stream/Transforms/Passes.cpp:384` | `stream.cmd.*` | 优化后的 stream cmd/resource IR | fixed-point cleanup、reuse allocations、SCF-to-CF、elide timepoints、fuse dispatch bindings、annotate dispatch arguments/assumptions、pack/fold dispatch operands。 |
| full transform | `Dialect/Stream/Transforms/Passes.cpp:474` | Flow executable/dispatch IR | final Stream IR | verify initialization order，顺序调用 tensor、async、cmd，按需 dump statistics，再运行 optimization、cleanup、SymbolDCE。 |

## 可单独调用的 pipeline 注册名

这些注册名是源码中为调试、复用或局部运行暴露的 pass pipeline；它们不是新的 VM 顶层阶段，而是上表阶段内部的可命名组合。

| 注册名 | 代码位置 | 所属范围 | 含义 |
| --- | --- | --- | --- |
| `iree-common-input-transformation-pipeline` | `InputConversion/Common/Passes.cpp:57` | `input` | 公共输入 import、module name sanitize、类型升降级。 |
| `iree-abi-transformation-pipeline` | `Bindings/Native/Transforms/Passes.cpp:42` | `abi` | Native IREE ABI wrapper pipeline。 |
| `iree-tflite-transform-pipeline` | `Bindings/TFLite/Transforms/Passes.cpp:36` | `abi` | TFLite binding wrapper pipeline。 |
| `iree-preprocessing-transpose-convolution-pipeline` | `Preprocessing/Passes.cpp:188` | `preprocessing` | 面向卷积布局与 transpose 规整的预处理组合。 |
| `iree-preprocessing-backward-data-conv-pipeline` | `Preprocessing/Passes.cpp:199` | `preprocessing` | backward-data convolution 相关预处理组合。 |
| `iree-preprocessing-make-single-dispatch` | `Preprocessing/Passes.cpp:210` | `preprocessing` | 倾向形成单 dispatch 的函数内预处理组合。 |
| `iree-global-optimization-transformation-pipeline` | `GlobalOptimization/Passes.cpp:302` | `global-optimization` | 全局优化阶段的独立注册入口。 |
| `iree-global-optimization-hoist-constant-expressions` | `GlobalOptimization/Passes.cpp:310` | `global-optimization` | 常量表达式 hoist 子 pipeline。 |
| `iree-dispatch-creation-pipeline` | `DispatchCreation/Passes.cpp:421` | `dispatch-creation` | dispatch creation 阶段的独立注册入口。 |
| `iree-dispatch-creation-preprocessing-pipeline` | `DispatchCreation/Passes.cpp:429` | `dispatch-creation` | dispatch region 创建前的预处理组合。 |
| `iree-flow-transformation-pipeline` | `Dialect/Flow/Transforms/Passes.cpp:270` | `flow` | Flow 阶段的独立注册入口。 |
| `iree-stream-cleanup-pipeline` | `Dialect/Stream/Transforms/Passes.cpp:537` | `stream` | Stream 公共 cleanup 子 pipeline。 |
| `iree-stream-tensor-transformation-pipeline` | `Dialect/Stream/Transforms/Passes.cpp:544` | `stream` | source/Flow 形态到 `stream.tensor.*` 的子 pipeline。 |
| `iree-stream-async-transformation-pipeline` | `Dialect/Stream/Transforms/Passes.cpp:550` | `stream` | `stream.tensor.*` 到 `stream.async.*` 的子 pipeline。 |
| `iree-stream-cmd-transformation-pipeline` | `Dialect/Stream/Transforms/Passes.cpp:556` | `stream` | `stream.async.*` 到 `stream.cmd.*` 的子 pipeline。 |
| `iree-stream-optimization-pipeline` | `Dialect/Stream/Transforms/Passes.cpp:562` | `stream` | Stream command/resource 优化子 pipeline。 |
| `iree-stream-transformation-pipeline` | `Dialect/Stream/Transforms/Passes.cpp:569` | `stream` | Stream 完整 transform pipeline。 |
| `iree-hal-transformation-pipeline` | `Dialect/HAL/Transforms/Passes.cpp:659` | `hal` | 标准 HAL transform pipeline。 |
| `iree-hal-inline-static-transformation-pipeline` | `Modules/HAL/Inline/Transforms/Passes.cpp:113` | `hal` | `InlineStatic` 执行模型使用的 HAL Inline pipeline。 |
| `iree-hal-inline-dynamic-transformation-pipeline` | `Modules/HAL/Loader/Transforms/Passes.cpp:135` | `hal` | `InlineDynamic` 执行模型使用的 HAL Loader pipeline。 |
| `iree-vm-transformation-pipeline` | `Dialect/VM/Transforms/Passes.cpp:206` | `vm` | VM dialect lowering pipeline。 |

## HAL 子阶段与后端边界

| VM 阶段名 | HAL 阶段名 | 代码位置 | 后端边界 |
| --- | --- | --- | --- |
| `executable-sources` | `PipelinePhase::ExecutableSources` | `Dialect/HAL/Transforms/Passes.h:30`、`Dialect/HAL/Transforms/Passes.cpp:333` | 不调用 target backend translation；只完成 device/interface/source 层准备。 |
| `executable-configurations` | `PipelinePhase::ExecutableConfigurations` | `Dialect/HAL/Transforms/Passes.cpp:366` | `ConfigureExecutablesPass` 在每个 target variant 上调用 `TargetBackend::buildConfigurationPassPipeline`。调用点见 `ConfigureExecutables.cpp:82`。 |
| `executable-targets` | `PipelinePhase::ExecutableTargets` | `Dialect/HAL/Transforms/Passes.cpp:429` | `TranslateAllExecutablesPass` 在每个 target variant 上调用 `TargetBackend::buildTranslationPassPipeline`。调用点见 `TranslateExecutables.cpp:86`。 |
| `hal` tail | HAL full transform after executable targets | `Dialect/HAL/Transforms/Passes.cpp:454` | 可选 `LinkAllExecutablesPass` 调用 `TargetBackend::buildLinkingPassPipeline`，再序列化 executable。调用点见 `LinkExecutables.cpp:57`。 |

目标后端接口本身定义在 `Dialect/HAL/Target/TargetBackend.h`。configuration pipeline 是可选 hook，translation pipeline 是纯虚函数，linking pipeline 是可选 hook，serialization hook 负责把 translated executable variant 替换为 binary op。

| TargetBackend hook | 调用 pass | 代码位置 | 阶段边界 |
| --- | --- | --- | --- |
| `buildConfigurationPassPipeline` | `ConfigureExecutablesPass` | `ConfigureExecutables.cpp:82`、`TargetBackend.h:189` | `executable-configurations` 内调用；可给 variant/export 标注 target-specific translation attrs。 |
| `buildTranslationPassPipeline` | `TranslateAllExecutablesPass` | `TranslateExecutables.cpp:86`、`TargetBackend.h:223` | `executable-targets` 内调用；backend 必须实现，输出 SPIR-V、LLVM dialect 或其他 target IR。 |
| `buildLinkingPassPipeline` | `LinkAllExecutablesPass` | `LinkExecutables.cpp:57`、`TargetBackend.h:275` | `hal` tail 内可选调用；backend 可合并 executable variants、clone entry points、更新引用。 |
| `serializeExecutable` | `SerializeAllExecutablesPass` | `SerializeExecutables.cpp:88`、`TargetBackend.h:298` | `hal` tail 内调用；backend 插入一个或多个 `hal.executable.binary`，成功后原 variant 被删除。 |

## 执行模型对阶段的影响

| 执行模型 | 影响位置 | 行为 |
| --- | --- | --- |
| `HostOnly` | `Pipelines.cpp:249`、`Pipelines.cpp:349`、`Pipelines.cpp:442` | 跳过 preprocessing/global optimization 及后续 flow/stream/hal 设备调度路径；注释说明无 tensor 时不需要 flow/stream/HAL。 |
| `AsyncInternal` / `AsyncExternal` | `Pipelines.cpp:447` | 走标准 HAL transform pipeline。`AsyncExternal` 还会让 ABI invocation model 选择 coarse fences（`Pipelines.cpp:170`）。 |
| `InlineStatic` | `Pipelines.cpp:453` | 走 `HAL::Inline::buildHALInlineStaticTransformPassPipeline`，该 pipeline 将 stream 转成 `hal_inline` 并传播 subranges。 |
| `InlineDynamic` | `Pipelines.cpp:457` | 走 `HAL::Loader::buildHALInlineDynamicTransformPassPipeline`，该 pipeline 侧重 executable serialization 与 loader materialization。 |

## 关键默认选项

这些默认值解释了“没有额外 flag”时各阶段为什么按当前形态运行；具体 flag 解析在 `Pipelines/Options.cpp`，结构默认值主要在 `Pipelines/Options.h`。

| 范围 | 默认值 | 代码位置 | 对阶段的影响 |
| --- | --- | --- | --- |
| binding | `native=true`、`tflite=false` | `Pipelines/Options.h:38` | 默认 ABI 阶段生成 Native IREE ABI wrapper，不生成 TFLite wrapper。 |
| input | `inputTypeMnemonic="auto"`、`demoteF64ToF32=true` | `Pipelines/Options.h:55`、`Pipelines/Options.h:77` | 默认自动选择 input conversion，并在 common input conversion 中把 f64 降为 f32。 |
| preprocessing | textual pipeline、Transform spec、PDL spec 默认为空 | `Pipelines/Options.h:98` | 默认不额外插入用户指定 preprocessing，只保留插件和 attr-based 入口。 |
| global optimization | `constEval=true`，但 default VM pipeline 中改成 `false` | `Pipelines/Options.h:157`、`Pipelines.cpp:494` | 结构默认允许 const-eval hook；命令行默认 pipeline 因没有 JIT hook 会关闭它。 |
| dispatch creation | aggressive fusion false、fuse multi-use true、data tiling false、pad handling false | `Pipelines/Options.h:267` | 默认形成 dispatch 时启用多用途 producer 融合，但不启用更激进 fusion/data tiling/native pad handling。 |
| stream | `optimizeBindings=true` | `Pipelines/Options.h:239` | Stream optimization 默认尝试 fuse dispatch bindings。 |
| HAL transform | `serializeExecutables=true`、`linkExecutables=true` | `Dialect/HAL/Transforms/Passes.cpp:29`、`Dialect/HAL/Transforms/Passes.cpp:36` | 标准 HAL tail 默认会链接并序列化 executables。 |
| VM target | index bits、float extension、stack size 等由 `VM::TargetOptions` 映射 | `Dialect/VM/Transforms/Passes.cpp:58` | 影响 VM conversion 对 index 宽度、浮点扩展、unsupported float truncation 和 stack-size 优化的处理。 |

## 读源码时的阶段边界判断

| 判断点 | 结论 |
| --- | --- |
| `compileFrom` / `compileTo` | 每个阶段都用枚举顺序控制 late-entry 和 early-exit；`compileTo` 命中当前阶段时立即返回。 |
| hooks | `beforePhase` 在阶段 pass 加入前调用；`afterPhase` 和 `pipelineExtensions` 在阶段 pass 加入后调用。HAL 子阶段通过 `IREEVMPipelineHooks::operator IREE::HAL::PipelineHooks()` 映射回 VM phase。 |
| `buildIREEPrecompileTransformPassPipeline` | 名称中的 precompile 指到 global optimization 为止，不包含 dispatch/flow/stream/HAL/VM。 |
| `buildIREEVMTransformPassPipeline` | 是完整 end-to-end input-to-VM pipeline；先运行 precompile，再按 execution model 补 dispatch/flow/stream/HAL/VM。 |
| `executable-*` | 不是独立于 HAL 的顶层 pipeline，而是 VM pipeline 暴露出来的 HAL 内部 early-exit 截点。 |
| `hal` vs `executable-targets` | `executable-targets` 只保证 executable variants 已翻译；`hal` 还包含 host program conversion、linking、serialization、runtime resource/device materialization。 |
| `end` | 不是额外 lowering 阶段，只表示完整 pipeline 不在 `vm` 后截断。 |
