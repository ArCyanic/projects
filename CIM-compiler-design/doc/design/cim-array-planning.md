# CIM Array Planning

## 处理流程

Array planner位于native executable linking后的logical优化与SRAM materialization之间：

```text
ordinary logical cim.mvm
  -> weight formation
  -> whole-deployment StaticArrayPlan
  -> fixed Array views + one init export
  -> runtime cim.mvm retargeting
```

Horizontal packing和weight replication已经由前置logical passes完成。Planner不识别优化流水线名，
不合并dataflow，也不产生SRAM offset。

## 输入与输出

输入是static、array-legal的ordinary logical MVM，以及native immutable weight global。Planner按logical
view chain的常量字节偏移和最终type的static strides读取weight；中间cast可以放宽type offset，并形成identity-layout `[K,N]` immutable global作为load source。

输出只有：

- competition profile拥有的单个Array root；
- unique weight chunks对应的non-overlapping native Array views；
- 唯一`__cim_array_init`中的embedded-to-Array `cim.array.load`；
- 只引用固定Array views的runtime `cim.mvm`。

`StaticArrayPlan` 在 pass 内供初始化生成与 MVM retargeting 共同消费。

## 放置

Planner读取linked variant的全部logical MVM weights，按完整canonical bytes去重，并用唯一deterministic
descending-area first-fit把所有unique chunks同时放入Array。候选行是0及已放置矩形的下边界；
每行按列扫描重叠的blocker，将候选列推至其右边界，取第一个可容纳的最左空位。若weight的N宽度超过Array列宽，只沿N
切成相邻blocks；K tiling和显式partial accumulation保持原有IREE/MLIR数据流。

所有regions在module initialization时一次写入并在推理期间共驻。相同shape和bytes的chunks共享region；
所有其他regions必须bounds内且互不重叠。baseline无合法布局时编译失败。

Packing与replication pass用同一个planner interface检查candidate后的完整deployment。Optional
candidate按组尝试：通过后立即应用，失败不撤销此前已接受的组。Replication依次降低复制因子，
直到候选可放置或只剩一个原MVM。清单按所有仍存活的weight uses构造，由planner按内容去重，
因此同一原权重若仍被其他MVM引用，就继续计入容量。block-diagonal structural zeros属于完整resident rectangle。

## SRAM关系

仅作为init `cim.array.load` source的immutable global保持embedded，不进入SRAM。Activation、result和其他
compute values随后由SRAM materializer导入独立allocations，再由选定allocator形成arena offsets。

## Competition约束

Array dimensions来自hardware profile，planner不硬编码模型或pipeline。Serializer机械投影唯一deployment
export和runtime exports；runtime不重新规划、不做first-use cache、隐式load或推理期间reprogramming。

## 为什么放在 linking hook

IREE 的 translation hook 只处理单个 executable；`TargetBackend::buildLinkingPassPipeline`
运行在 host 已转换为 HAL、export ordinals 与 resource caches 尚未物化的窗口。它能同时看到全部
目标 executable 和 host module，因此可以合并权重并插入唯一初始化调用。CIM 编译要求保留原生
executable linking；关闭 linking 的调试模式不运行这条物理化路径。

`CIMArrayInitialization.cpp` 使用原生 `DeviceAnalysis` 证明所有 executable lookup 具有同一个
device owner，在 `util.initializer` 中创建 one-shot command buffer、dispatch 初始化 export，
提交队列并等待 fence。后续原生 ordinal resolution 与 resource cache passes 处理这些 symbol references。
Serializer 只消费完成物理化的 variant，不补跑 pass pipeline。
