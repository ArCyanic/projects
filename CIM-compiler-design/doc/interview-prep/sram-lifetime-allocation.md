# SRAM 怎样在计算不变时减少占用

权重复制改变一次阵列计算覆盖的范围，SRAM 复用接着回答另一个问题：这些计算需要的输入、结果和暂存，是否必须各占一段不同地址？

关键在于使用时间。一个结果已经完成最后一次读取后，它占过的地址就可以交给后面的暂存。先用三个缓冲区推一次地址规划，再看 MLIR 如何从 IR 中得到这些信息。

## 先手算三个对象的地址

设所有对象按 64 B 对齐，实际访问范围如下。时间表示程序中的操作位置：

| 对象 | 大小 | 活跃区间 |
| --- | ---: | --- |
| A | 256 B | `[0,4)` |
| B | 512 B | `[2,8)` |
| C | 256 B | `[5,10)` |

顺序分配给每个对象追加空间：A 放在 0，B 放在 256，C 放在 768，地址峰值是 1024 B。

当 C 开始使用时，A 已结束，B 仍存活。因此 C 可以接过 A 的位置：

```text
地址 [0,256)    ：先给 A，A 结束后给 C
地址 [256,768)  ：给 B

峰值 768 B；A 与 C 复用 offset 0。
```

计算依赖和执行次序都保持原样，改变的是对象与地址的对应关系。要自动完成这一步，编译器需要知道每个对象的大小，以及它真正使用到什么时候。

## 先补齐对象，才能知道要分配什么

进入物理化时，输入可能来自 HAL binding，偏置来自常量 global，内部结果则已有 `memref.alloc`。`CIMMaterializeSRAMPass` 将需要进入 SRAM 的外部数据变为紧凑分配，建立输入、常量导入与结果写回的 `memref.copy`；已有临时分配继续保留。[SRAM 物化](../../compiler_plugins/cim/src/cim/Codegen/CIMMaterializeSRAM.cpp)

输出区域若在读取前已被完整写入，就可以省去它的导入；这项判断按实际读写区域进行。这样形成的分配与拷贝，准确表达计算需要保存的数据。

位串行展开随后为每条 MVM 补上一块 `[1,N]xi32` scratch：第 0 bit 写结果，后面的 bit 轮流使用这块暂存，再缩放并加回结果。暂存只在展开后出现，因此 SRAM 地址分配安排在 bit-serial expansion 之后。

现在大小可以直接从静态 MemRef 类型计算。例如 64 个 i32 是 256 B，128 个 i32 是 512 B，对应前面的 A/C 与 B。

## 为什么最后使用必须连同 view 一起看

MemRef 的 subview、reshape 等操作创建的是存储视图。一个根 allocation 可能只在早期创建 view，但这块存储还要供后面使用：

```mlir
%a = memref.alloc() : memref<64xi32>
%part = memref.subview %a[16] [16] [1]
    : memref<64xi32> to memref<16xi32, strided<[1], offset: 16>>
// 中间还有其他计算。
memref.copy %part, %output
    : memref<16xi32, strided<[1], offset: 16>> to memref<16xi32>
```

A 的生命周期必须延续到最后一次读取 `%part`。这就是 alias 分析在这里的作用：沿根分配找到所有派生视图，再确定整块存储的最后使用位置。

CIM 的适配层先给 allocations 设置 64 B 对齐，并在 return 前补上 `memref.dealloc`。这为原生 pass 提供一组明确的 alloc/dealloc 对。[CIMAllocateSRAM.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMAllocateSRAM.cpp)

`OptimizeAllocationLiveness` 使用 `BufferViewFlowAnalysis` 找到最后的 alias use，将 dealloc 提前到它之后。`StaticMemoryPlannerAnalysis` 再从 alloc/dealloc 的位置得到活跃区间，计算偏移并改写 arena。生命周期分析与地址改写都由 MLIR 原生机制完成。

## Best-fit 如何复用 A 的空间

规划器按对象的开始位置处理分配。处理 C 时，B 对应的 `[256,768)` 仍被占用，A 原来的 `[0,256)` 已成为空洞。

`bestFitMemoryPlanner` 将候选地址按要求对齐，选择能容纳 C 的最小空洞；此处 256 B 正好放下 C。若当前 arena 中没有足够大的空洞，再扩展末端。[原生算法](../../iree/third_party/llvm-project/mlir/lib/Dialect/Bufferization/Transforms/StaticMemoryPlanning.cpp)

`sequential` 使用 `trivialMemoryPlanner`，始终顺序追加；`reuse` 则先收缩生命周期，再使用 BestFit。两者共用相同的计算程序，因而可以直接比较地址峰值。

## 分配结果怎样回到普通 IR

对前面的三个对象，最终可以用一个 768 B arena 和三个 typed views 表达：

```mlir
%c0 = arith.constant 0 : index
%c256 = arith.constant 256 : index
%arena = memref.alloc() alignment = 64 : memref<768xi8>
%a = memref.view %arena[%c0][]
    : memref<768xi8> to memref<64xi32>
%b = memref.view %arena[%c256][]
    : memref<768xi8> to memref<128xi32>
%c = memref.view %arena[%c0][]
    : memref<768xi8> to memref<64xi32>
```

A 与 C 的 view 起点相同，它们各自在自己的活跃区间内访问存储。原生 pass 替换原 allocations 的使用并消去 alloc/dealloc 对，后面的地址归约直接读取这些 views。

每个工作组入口独立规划 arena。综合用例 `integrated_showcase` 的最大入口峰值由 sequential 的 16384 B 降到 reuse 的 10240 B；计算与权重布局相同，变化体现在 arena 长度和 view offsets。

沿这条路径看，SRAM 复用依赖的三件事都已落在 IR 中：allocation 给出大小，alias uses 决定何时结束，typed view 保存最终地址。Runtime 按这些固定地址执行同一份计算。
