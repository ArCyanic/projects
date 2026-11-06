# 权重复制怎样把多行计算合成一次

[上一篇](iree-fusion-and-weight-replication.md)已经把问题收束到一个工作组：四条 MVM 使用相同 W、不同输入行。现在先把矩阵缩小，算清楚它们为什么能合并，再看代码需要什么信息。

## 用两行输入看清块对角改写

取一个小权重矩阵：

```text
W = [1 2]        x0 = [1 2]        x0 @ W = [ 7 10]
    [3 4]        x1 = [5 6]        x1 @ W = [23 34]
```

把两份 W 放到对角块，其他位置填零：

```text
                 [1 2 0 0]
[1 2 | 5 6]  @   [3 4 0 0]  =  [7 10 | 23 34]
                 [0 0 1 2]
                 [0 0 3 4]
```

左半输入只贡献左半输出，右半输入只贡献右半输出。结构零隔开了两行之间的交叉项，所以一次更宽的 MVM 可以保留两次原计算的结果。

对 r 行输入，同样得到 `[1,rK] × [rK,rN] → [1,rN]`。这就是 `DenseWeight::blockDiagonal` 构造的新权重。[矩阵构造](../../compiler_plugins/cim/src/cim/Codegen/StaticArrayPlacement.cpp)

## 代码怎样找到可以这样摆放的行

回到真实用例：W 为 `[256,128]xi8`，一个工作组处理四行。`replicateRows` 收集链接后 MVM，沿相邻操作寻找同形、同内容的权重，以及连续的输入行和输出行。[实现](../../compiler_plugins/cim/src/cim/Codegen/CIMOptimizeMVM.cpp)

四条 MVM 的输入来自同一个 `[4,256]` 区域，输出来自同一个 `[4,128]` 区域，因而可以直接扩大视图：

```text
输入：四个 [1,256] 行视图 → [4,256] → [1024] → [1,1024]
输出：四个 [1,128] 行视图 → [4,128] → [512]  → [1,512]
```

`areConsecutiveMVMRows` 检查行视图的来源、偏移和连续性；`packMVMRows` 用 subview、collapse、expand 表达上面的变化。它们调整访问同一段存储的方式，激活值和输出数据继续留在原缓冲区。[视图处理](../../compiler_plugins/cim/src/cim/Codegen/CIMMVMUtils.cpp)

合并还会把后面几行的访问提前到第一条 MVM 的位置。假如中间有操作修改了 x1，提前读取它就会改变结果。因此 `canFuseMVMs` 结合别名与读写效应检查操作顺序，确认这一移动可行。

## 为什么先试排权重清单

四份 W 组成 `[1024,512]` 的稠密矩形，正好占满阵列。如果其他入口还要使用另一块权重，这个四行候选就可能无法与它共存。

代码先由行数和阵列尺寸得到复制上限：

```text
r_max = min(连续行数, 阵列行数 / K, i8 单元列数 / N)
```

然后构造候选字节，并由 `fitsReplacement` 形成试排清单：把本组 MVM 对应的权重使用替换成候选矩阵，保留其他仍存活的使用，再调用同一个 `planStaticArray`。试排期间只操作权重值与引用，IR 保持原样。

若四行候选放不下，`replicateRows` 继续尝试三行、两行。例如只合并前三行时，第四条 MVM 仍使用原 W，清单就需要同时包含 `diag(W,W,W)` 和 W。按仍存活的使用构造清单，才能正确计算这种部署成本。

候选可放置后，才创建新的 immutable weight global、扩大输入输出视图、生成新 MVM，并删除原来的操作。

## 接受候选后，IR 怎样变化

以下节选展示输入视图的转换，输出沿相同方式处理：

```mlir
// %rows 已覆盖工作组的四行输入。
%flat = memref.collapse_shape %rows [[0, 1]]
    : memref<4x256xi32> into memref<1024xi32>
%packed = memref.expand_shape %flat [[0, 1]] output_shape [1, 1024]
    : memref<1024xi32> into memref<1x1024xi32>

// %block_weight 指向新建的 diag(W,W,W,W) 常量。
cim.mvm ins(%packed, %block_weight
    : memref<1x1024xi32>, memref<1024x512xi8>)
    outs(%packed_output : memref<1x512xi32>)
```

块对角权重在这里仍是逻辑常量。后续 `CIMPlanArrayPass` 为它安排固定 Array view，并在初始化入口生成权重写入。

## 为什么轮次下降，空间却会上升

`CIMExpandBitSerialPass` 根据每条 MVM 的激活位宽展开 bit 操作。本例 i32 激活需要 32 轮：四条 MVM 原本共 128 轮，合成一条后是 32 轮。[位串行展开](../../compiler_plugins/cim/src/cim/Codegen/CIMExpandBitSerial.cpp)

对应的权重面积从 `256×128=32768` 增为 `1024×512=524288` 个单元。其中 131072 个单元来自四份 W，另有 393216 个结构零。更宽的输出也需要更宽的 i32 位暂存。

所以复制用阵列空间换取较少的执行窗口。输入输出视图的连续性使这次计算合并无需额外搬运数据，完整权重试排控制常驻面积；扩大后的暂存则交给[SRAM 活跃期分配](sram-lifetime-allocation.md)继续处理。
