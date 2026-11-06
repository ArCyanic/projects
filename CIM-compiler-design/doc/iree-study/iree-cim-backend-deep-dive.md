# 从 GPU Codegen 到 CIM 存算阵列：本项目如何接入 IREE 的编译与运行全流程

读过 [IREE 全流程](iree_deep_dive_framework.md)和 [Stage 9、10、11 深度剖析](iree_stages_9_10_11_deep_dive.md)之后，我们已经见过一个矩阵乘如何变成 GPU 上的线程分工：Stage 9 选定 `tile_sizes` 和 `workgroup_size`，Stage 10 把计算分给线程、生成向量指令，Stage 11 再把设备代码与 Host 的命令提交接起来。

那么，把目标换成本项目的 CIM（Compute-In-Memory，存内计算）架构，是不是只要把最后的 `spirv.GL.Fma` 换成一条 CIM 指令就够了？

问题恰恰出在这里：**CIM 改变的不只是“用什么指令做乘法”，还有“权重存在哪里、输入怎样进入计算、结果经过多少轮才能得到”。** GPU 可以不断从内存读取权重参与运算；本项目的目标设备要求静态权重先写入存算阵列，推理时用激活值逐位驱动阵列，再在 SRAM 中重建整数结果。

这会把原来一个矩阵乘拆成几个相互关联的问题：权重能不能一起放下？同一块阵列怎样服务多个 dispatch？一次整数乘法为什么要展开成 8 轮甚至 32 轮？而 IREE 的 workgroup、binding、Host/Device 双轨，又怎样承接这些变化？

本文沿着这些问题，解释本项目为什么在一些地方继续使用 IREE 原生机制，又为什么把阵列布局和 SRAM 分配留到更晚的阶段。

## 一、先换一个硬件视角：矩阵乘不再只是“线程读取数据再做乘加”

### 1. 目标设备里究竟有什么？

本项目当前使用的 `competition` profile 描述一个单阵列设备。先把规模和单位分清，后面的分块数字就不会显得莫名其妙：

| 硬件资源 | 规模 | 在计算中承担什么工作？ |
| --- | --- | --- |
| 存算阵列 Array | `1024 × 4096 bit` | 部署时写入权重；计算时选中权重矩形，由 activation 的某一位驱动 |
| 按 i8 权重计数的 Array | `1024 × 512` 个单元，共 512 KiB | 一个 i8 权重占 8 个物理 bit 列，因此每行容纳 512 个权重 |
| SRAM | 512 KiB，分配对齐为 64 Byte | 保存动态输入、输出、部分和，以及逐位重建需要的暂存 |

注意那个 `4096 bit`。它不是 4096 个 i8 权重，而是 `4096 / 8 = 512` 个。后续权重放置、N 维分块和 ISA 的阵列视图，使用的都是这个换算后的单元坐标。

Array 和 SRAM 都是 512 KiB，却不能混为同一块“片上内存”：前者保存常驻权重并参与乘法，后者保存会随推理变化的数据。两者需要不同的规划方式。

硬件参数由 [HardwareProfile.cpp](../../compiler_plugins/cim/src/cim/Common/HardwareProfile.cpp)解析，并与编译器和运行时共享的 [CIMExecutableFormat.h](../../compiler_plugins/cim/src/cim/Common/CIMExecutableFormat.h)对应。

### 2. 贯穿案例：同一个整数矩阵乘，要补上哪些硬件决定？

我们选一个足够小、又能看出组内重组效果的例子：

```text
X : i8 [16,32]      # 运行时输入
W : i8 [32,64]      # 编译期静态权重
Y : i32[16,64]     # 输出

Y = X @ W
```

对 X 的某一行，数学含义仍是：

\[
y_n=\sum_{k=0}^{31}x_k w_{k,n}.
\]

但在这台设备上，执行过程更接近下面这样：

```text
模型部署时：
    把 W 写进 Array 的某个固定矩形

每次推理时：
    把一行 X 搬进 SRAM
    用 X 的第 0 位驱动该权重矩形，得到一组部分和
    用 X 的第 1 位驱动同一矩形，得到另一组部分和
    ……
    按各位的权重，把这些部分和重建为 i32 结果
    把结果写回 Y 对应的外部 buffer
```

也就是说，`W` 的物理位置和 `X` 的位轮次，都必须成为设备程序的一部分。只有矩阵乘的算术公式，还不足以运行这段计算。

接下来我们一直跟着三个对象：`W` 怎样从常量张量变成阵列矩形，`X` 怎样从 HAL binding 进入 SRAM，`Y` 又怎样从多个逐位部分和变回一个完整整数结果。

## 二、接入位置：为什么大部分 IREE 管线还能继续用？

### 1. Host 仍然调度任务，Device 换一种执行方式

回想前两篇文档的双轨视角：Host 要知道“哪些任务先后执行、哪些 buffer 传给它们”，Device 要知道“一次任务内部到底怎么算”。

把 GPU 换成 CIM，并不会让输入输出、数据依赖和任务完成信号凭空消失。因此，本项目仍然让 IREE 负责 dispatch 形成、Flow outlining、Stream 资源调度和 VM lowering。变化集中在前端规范化，以及 Device 程序的生成、链接和加载。

[PluginRegistration.cpp](../../compiler_plugins/cim/src/PluginRegistration.cpp)中的 `CIMSession` 是接入口。它注册 `cim` 方言和 passes，提供名为 `cim` 的 HAL target backend，并在两个较早的扩展口加入处理：

- `input`：规范化项目支持的 ONNX 整数线性算子，让原生优化能够继续分析。
- `preprocessing`：执行选定管线中的异构融合，再调用 IREE 原生横向 contraction 融合。

这里的预处理可以改变后续任务的组织方式，但 dispatch 边界仍由原生 dispatch formation 生成。到 Device codegen 阶段，再由 CIM backend 接手具体硬件问题。

### 2. 用原生阶段重新定位本项目的改动

| IREE 阶段 | 原来的问题 | 本项目如何回答？ |
| --- | --- | --- |
| Stage 8：`executable-sources` | 这个 executable 发往哪里，使用什么接口与格式？ | 声明 `cim` backend、`cim-executable` 格式和硬件 profile，交给 HAL 建立 variant 与 binding 接口 |
| Stage 9：`executable-configurations` | 一次任务覆盖多少计算，组内怎样分解？ | 选择 `cim-workgroup` 管线，确定 workgroup tile 与 Array tile |
| Stage 10：`executable-targets` | 把配置真正改写成什么目标程序？ | 完成 tiling、bufferization，生成逻辑 `cim.mvm`、`cim.elt` 和 memref 视图 |
| Stage 11：`hal` 的 linking hook | 多个目标程序怎样共同部署？ | 链接全部 CIM executable，重组 MVM、统一放置权重、物化 SRAM、展开 bit-serial 并分配地址 |
| Stage 11：serialization | Runtime 最终读取什么？ | 将物理程序编码为 `cim-executable` payload，同时生成对应的 ISA 文本 |
| Stage 12：`vm` | Host 调用如何执行？ | 沿用原生 VM lowering，设备 payload 随 Host 字节码进入 VMFB |

从 [CIMTargetBackend.cpp](../../compiler_plugins/cim/src/cim/Target/CIMTargetBackend.cpp)可以看到这几组 hook 的连接关系。

这里先记住一个与 GPU 案例不同的地方：**Stage 10 结束时，本项目还没有把所有物理决定做完。** 目标 IR 仍可以是自定义 CIM 方言，后面的链接阶段会继续加工它。为什么要留到这么晚？等我们讨论“多个任务共用一张阵列”时，原因就清楚了。

## 三、在进入后端之前：为什么不把 ONNX 矩阵乘直接改成 CIM 指令？

### 1. 过早丢掉张量结构，会失去什么？

假设刚读入一个矩阵乘，就立刻把它拆成 SRAM 地址、逐位操作和阵列坐标。接下来，IREE 想把偏置融合进矩阵乘，或者判断两条分支能否进入同一个 dispatch，看到的就已经是一串低层内存操作了。

所以，[前端规范化 pass](../../compiler_plugins/cim/src/cim/Frontend/CIMNormalizeONNXLinear.cpp)先把项目输入约定下的部分 `onnx.Gemm` 和 `onnx.MatMulInteger` 整理成 Linalg contraction。输出继续使用 `tensor.empty`、零初始化和结构化矩阵乘，让原生优化保留分析空间。

本项目处理的前端权重按 `[N,K]` 组织，对应索引关系为：

```text
迭代空间：(m,n,k)
activation：X[m,k]
weight：    W_frontend[n,k]
output：    Y[m,n]
```

本文一直使用 `W[K,N]` 表示其数学视图。两种表示怎样对应，由 indexing maps 和后面的转置视图处理。只看 `matmul` 这个名字，不能判断权重的真实存储方向。

规范化的支持范围也比较具体：权重为有符号 i8，激活为有符号 i8 或 i32；这条 Gemm 路径要求 `transA=0`、`alpha=1`、`beta=1`。它不是一个已经支持所有量化参数和转置组合的通用 ONNX 后端。

### 2. 两条分支怎样变成一次阵列计算？

如果两条独立分支分别计算：

\[
Y_0=X_0W_0,\qquad Y_1=X_1W_1,
\]

可以考虑把它们写成一个块对角矩阵乘：

\[
[\,Y_0\;Y_1\,]
=[\,X_0\;X_1\,]
\begin{bmatrix}W_0&0\\0&W_1\end{bmatrix}.
\]

它为什么仍然算出原来的结果？因为非对角区域全是零，`X0` 只会影响 `Y0`，`X1` 只会影响 `Y1`。两个独立计算因此可以放进一个更大的阵列窗口。

不过，这会改变输入拼接、权重形状和结果切片，还可能改变 dispatch 边界。因此，[异构融合](../../compiler_plugins/cim/src/cim/Codegen/CIMFuseHeterogeneousContractions.cpp)发生在 preprocessing，并先用完整静态权重 inventory 试算容量。

共享 activation 的 contraction 则可交给原生横向融合处理，本项目调用时设置 `fusionLimit=4`，仍保留原生匹配条件。它先让相关计算有机会进入同一个任务；真正把 MVM 权重拼成一个物理窗口，是后面链接后的工作。

到这里，计算图可以根据 CIM 的特点重新组织，但还没有任何固定的 Array 坐标或 SRAM 地址。

## 四、Stage 9：CIM 没有一排 GPU 线程，为什么还要 workgroup？

### 1. Workgroup 描述任务覆盖范围，不必照搬 GPU 的线程组织

GPU 案例中，D0 的一个 workgroup 有 256 个线程，每线程负责四个输出。很容易顺着这个印象问：CIM 的一个 workgroup 里，也要安排多少个类似 CUDA thread 的执行者吗？

本项目没有这样做。它保留 workgroup 作为任务实例，让每组处理若干输入行；组内则是一段按顺序执行的阵列操作和数据搬运程序。

后端把 `hal.interface.workgroup.size` 转成 `1`，运行时也报告组内大小 `[1,1,1]`。因此，“每组处理 8 行”说的是这份程序覆盖的数据，不能读成“8 个线程各算一行”。

### 2. 拆开 `lowering_config`，逐个看清数字

[CIMSelectLoweringStrategyPass.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMSelectLoweringStrategyPass.cpp)在 contraction 的 `(M,N,K)` 空间里设置两级 tile：

```text
第 0 级：workgroup tile = [mTile, 0, 0]
第 1 级：Array tile     = [1, nTile, kTile]
translation pipeline  = cim-workgroup
```

| 层级 | 决定什么？ | 为什么这样分？ |
| --- | --- | --- |
| Workgroup tile | 一组覆盖 M 维中的多少行 | Host 按 workgroup 数量启动任务，各组使用不同输入、输出切片 |
| Array tile | 组内每次逻辑 MVM 的 `[1,Ktile] × [Ktile,Ntile]` | 阵列单次最多覆盖 1024 个权重行、512 个 i8 权重列 |

当前算法用 `uniformTileSize(size, capacity)` 选择等长、能整除原维度的 tile。它先估算需要多少块，再增加块数直到可以整除，因此无需尾块 padding；某些尺寸也会因此得到更小的 tile。

回到 `(M,N,K)=(16,64,32)`：

```text
kTile = 32     # 小于阵列的 1024 行
nTile = 64     # 小于阵列的 512 个 i8 列

mCap = min(16, floor(1024/32), floor(512/64))
     = min(16, 32, 8)
     = 8

mTile = 8
workgroup tile = [8,0,0]
Array tile     = [1,64,32]
workgroup 数量 = 16/8 = 2
```

于是，这个矩阵乘被分成两组任务，每组处理 8 行；组内每个逻辑 MVM 处理一行，形状为 `[1,32] × [32,64] → [1,64]`。

还有一个值得追问的细节：**M 是输入行数，为什么 `mCap` 却同时要除以权重的 K 和 N？**

因为后续可以复制权重，把 r 行输入合成一个块对角 MVM。此时权重矩形从 `[K,N]` 变成 `[rK,rN]`，两个方向都要有空间。Stage 9 用这两个比值控制组内行数，为后续重组留下机会；究竟能复制多少，还得看全模型的权重布局。

## 五、Stage 10：一个矩阵乘怎样成为逻辑 CIM 程序？

### 1. 从“带配置的张量”到“带视图的 MVM”

[CIMPasses.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMPasses.cpp)中的 `cim-workgroup` 管线读取配置，先做 workgroup tiling，再进行 Array tile 合法化、相关 Linalg 分解与 bufferization，最后转换为 CIM 操作。

这里沿用了前两篇文档里的顺序：先利用张量和结构化迭代空间做分块，再通过 bufferization 确定实际存储与别名。等转成 CIM 时，才能准确处理“输入在哪里读、结果写到哪里、能不能覆盖旧值”。

原生 HAL 入口保持无显式参数。函数内部用 `hal.interface.binding.subspan` 获取外部数据视图，用 `hal.interface.workgroup.id` 获取任务坐标。省略视图构造后，一组任务的含义是：

```text
wg = hal.interface.workgroup.id.x

for row in 0..7:
    xrow = X[wg*8 + row, 0:32]
    yrow = Y[wg*8 + row, 0:64]
    cim.mvm(xrow, W, yrow)
```

组内静态循环随后通过原生 annotated-loop unroll 展开，workgroup ID 则保留下来。这样，不同组使用的是同一份程序，只是读写不同输入、输出行。

### 2. 最容易改错的一步：矩阵乘的“累加”去了哪里？

`cim.mvm` 的语义很明确：

\[
\mathrm{dst}=\mathrm{src}\times\mathrm{weight}.
\]

它接收 `[1,K]` activation、`[K,N]` 权重，覆盖写入 `[1,N]` 的 i32 结果。

但 Linalg contraction 的 `outs` 往往表示累加初值，实际含义是：

\[
\mathrm{dst}_{new}=\mathrm{dst}_{old}+\mathrm{src}\times\mathrm{weight}.
\]

如果机械地把每个 Linalg 矩阵乘改成一个 `cim.mvm`，旧累加器就丢了。对零初始化的普通矩阵乘，这个问题可能看不出来；一旦切分 K 维，结果就会出错。

例如 `K=1536` 时，当前配置可以选择两个 `Ktile=768` 的等长块。它们应当贡献到同一个 Y：

```text
Y = X[:,0:768] @ W[0:768,:]
Y = Y + X[:,768:1536] @ W[768:1536,:]
```

第二块如果直接用 MVM 写 Y，就把第一块结果覆盖了。

因此，[LinalgToCIM.cpp](../../compiler_plugins/cim/src/cim/Codegen/Conversion/LinalgToCIM.cpp)会检查零初始化、别名和中间内存访问。可以证明目标提供零初值时，使用一个覆盖式 MVM；否则显式生成部分结果和加法：

```text
partial = alloc_like(dst)
cim.mvm(src, weight, partial)
cim.elt add(dst, partial, dst)
```

N 维切分则没有这个累加问题：不同 N tile 写入不同输出列。它需要输出切片，K tile 则需要部分和。两种切分会留下不同的暂存和访存关系，后面的 SRAM 规划都要看见。

### 3. 为什么不在此时把阵列坐标也写进去？

Stage 10 生成的 `cim.mvm` 还在引用普通 memref 权重视图。权重内容是静态的，但具体放在哪个阵列矩形，尚未确定。这样，后续仍然可以拼接权重、复制权重，或让内容相同的权重共享区域。

`cim.elt` 则表达向量加、减、乘、除，支持向量—向量 `vv` 和向量—立即数 `vi` 模式。[CIMOps.td](../../compiler_plugins/cim/src/cim/IR/CIMOps.td)还声明读写效应，让别名分析能够判断操作之间是否有依赖、暂存何时不再使用。

所以，Stage 10 的输出已经有了 CIM 的计算语义，却仍留有物理布局的余地。接下来，编译器需要把视野从一个任务扩大到整个部署。

## 六、Stage 11：为什么“链接”会成为 CIM 适配的核心？

### 1. 每个任务都能放下，不代表所有任务能一起部署

假设模型有两个 dispatch，各自使用 300 KiB 的不同静态权重。单独看，两份权重都小于 512 KiB；放到同一张 Array，就超了容量。

还有一种更隐蔽的情况：两份权重合起来没有超容量，但每个后端编译单元都从坐标零开始放，运行时仍会互相覆盖。

这就是为什么本项目先调用 [CIMLinkExecutables.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMLinkExecutables.cpp)，使用 IREE 的 executable linking 工具汇集全部 CIM 程序，并更新 Host 对 export 的引用。不同 compute 入口依然是不同任务，但现在编译器能够看见它们共同需要的全部权重。

随后，[CIMPlanArray.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMPlanArray.cpp)完成统一规划：

```text
全部 compute export 的逻辑 MVM
    ↓ 解析静态权重内容
按矩形形状与内容去重，按需切分列区域
    ↓ 在整个 Array 上做确定性放置
一个 __cim_array 根对象 + 各个固定 subview
    ↓
把每个 MVM 的权重引用改为对应物理矩形
```

[StaticArrayPlacement.cpp](../../compiler_plugins/cim/src/cim/Codegen/StaticArrayPlacement.cpp)使用启发式矩形放置：优先放置较大矩形，尝试已有矩形边缘形成的候选行，再向右寻找空位。这是在处理二维几何约束，单看总字节数并不够；同样，启发式失败也不等于数学上不存在任何可行布局。

当前实现要求静态权重常驻，不会自动为装不下的模型生成运行期换入换出。因此，把大矩阵切成合法 K/N tile，只说明每次 MVM 尺寸合法，不能绕过全模型的驻留容量限制。

### 2. 权重只部署一次，Host 怎么知道何时加载它？

阵列位置确定之后，后端生成唯一的 `__cim_array_init` export。它用 `cim.array.load` 把 payload 中的静态权重写进规划好的 Array 区域。

但仅仅生成这个函数还不够：谁调用它？如果第一次 compute dispatch 先执行，读到的仍是一块没有部署好的阵列。

[CIMArrayInitialization.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMArrayInitialization.cpp)因此在 Host 侧生成 `util.initializer`，通过标准 HAL 调用启动部署入口：

```text
取得 device 和 executable
    → 查找 __cim_array_init
    → 录制一次性 command buffer
    → dispatch(1,1,1)
    → queue.execute
    → 等待 signal fence，检查初始化状态
```

这与前两篇文档中 Host 侧“录制命令、提交、等待”的逻辑完全接得上。设备初始化也成为模型程序的一部分，VM lowering 会继续处理它。

模块实例建立时完成部署，后续计算使用相应 executable 实例持有的 Array 状态。SRAM 则在每次工作组调用中使用。loader 创建状态存储，Host 初始化程序发起实际权重写入，两者各有职责。

## 七、先别急着展开位轮次：逻辑 MVM 还能做什么优化？

如果 Stage 10 就把每个矩阵乘全部拆成 bit 操作，链接时看到的将是很多轮相似的读写与累加，权重之间的矩阵关系反而不容易改写。

保留逻辑 MVM，使 [CIMOptimizeMVM.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMOptimizeMVM.cpp)能在物理化前完成两种重组。

### 1. 横向 packing：相同输入为什么要重复驱动两次？

设同一入口内有：

\[
y_0=xW_0,\qquad y_1=xW_1.
\]

两个 MVM 都使用同一个 x。如果权重列数和依赖允许，可以把 W 横向拼起来：

\[
[\,y_0\;y_1\,]=x[\,W_0\;W_1\,].
\]

K 不变，N 变为 `N0+N1`。原来同一批输入位要驱动两套 MVM，现在可以在同一个窗口得到两组输出。

输出若恰好连续，可直接扩大输出视图；不连续时，则先写合并暂存，再复制回原位置。因此，packing 减少了阵列轮次，也可能增加 SRAM 与搬运。

这还解释了早期横向融合和此处 packing 为什么是两步：早期处理计算图和任务组织，此处才真正拼接逻辑 MVM 及权重。两个阶段掌握的信息不同。

### 2. 权重 replication：用更大的矩形，同时处理多行

再看另一种重复：同一权重 W 被连续多行输入使用。

\[
y_0=x_0W,\qquad y_1=x_1W.
\]

既然阵列还有空间，能否把两份 W 放到对角线上，一次处理两行？

\[
[\,y_0\;y_1\,]
=[\,x_0\;x_1\,]
\begin{bmatrix}W&0\\0&W\end{bmatrix}.
\]

这样，每一位输入驱动更大的矩形，就能同时产生两行对应的部分结果。

现在回到贯穿案例。Stage 9 已经让每组处理 8 行，W 的形状是 `[32,64]`。如果这里只考虑这个矩阵乘，并且全局容量检查通过，8 个逐行 MVM 可以合成：

```text
activation：[1,256]       = 8 行 × 每行 32 项
weight：    [256,512]     = diag(W,W,W,W,W,W,W,W)
result：    [1,512]       = 8 行 × 每行 64 项
```

对 i8 输入，两种方案的阵列操作次数是：

| 方案 | 每个 workgroup 的 MVM 组织 | `cim.bit` 次数 |
| --- | --- | ---: |
| 直接逐行执行 | 8 个 `[1,32] × [32,64]` | `8 行 × 8 位 = 64` |
| 8 行块对角复制 | 1 个 `[1,256] × [256,512]` | `1 个窗口 × 8 位 = 8` |

不过，复制并不免费。原权重矩形是 `32×64=2048 Byte`，新矩形却是 `256×512=131072 Byte`。为什么不是简单乘以 8？因为当前布局按包含零块的稠密矩形计量，行列都扩大 8 倍，面积扩大了 64 倍。

因此，优化器不会只看“少了几轮”。它要检查同权重、连续输入行和内存依赖，还要把替换后的矩形连同其他所有权重交给同一个放置器试算。放不下就减小复制数量，或保留原计算。

bit 次数从 64 变成 8，也不能直接推导实际延迟缩短 8 倍：每轮覆盖的窗口变大了，向量运算和搬运成本也可能变化。

## 八、bit-serial 展开：整数乘法的符号位藏在哪里？

### 1. 一轮 Array 运算只看 activation 的一位

物理 `cim.bit` 的含义是：

\[
p_b[n]=\sum_k ((x_k\gg b)\mathbin{\&}1)\,w_{k,n}.
\]

选中的输入位只有 0 和 1。一轮得出的 p 还不是完整的 `xW`，必须按该位的位权重建。

对于有符号 B-bit 补码：

\[
x=\sum_{b=0}^{B-2}2^b x_b-2^{B-1}x_{B-1},
\]

于是：

\[
y=\sum_{b=0}^{B-2}2^b p_b-2^{B-1}p_{B-1}.
\]

最后一位为什么是减？拿 i8 的 `-1=11111111₂` 看就很直观：前七位加出 127，最高位要贡献 -128，合起来才是 -1。若把最高位也当正数加进去，得到的就是 255。

### 2. `cim.mvm` 如何拆成真正执行的操作？

[CIMExpandBitSerial.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMExpandBitSerial.cpp)将每个逻辑 MVM 改写为：

```text
bit(x, W, dst, bit_index=0)      # 最低位直接写 dst
scratch = alloc_like(dst)

for b in 1..B-1:                # 编译期展开
    bit(x, W, scratch, bit_index=b)
    elt.mul(scratch, 2^b, scratch)
    if b == B-1:
        elt.sub(dst, scratch, dst)
    else:
        elt.add(dst, scratch, dst)
```

从这里能看出两件事。第一，i8 activation 要 8 轮，i32 要 32 轮，位宽直接影响设备程序的长度。第二，逻辑 MVM 并没有消失得无影无踪，它留下了明确的 bit、缩放、加减操作，还新增了一块 scratch。

这块新暂存，也决定了 SRAM 地址分配不能过早进行。

## 九、SRAM 规划：Host 已经分过内存，为什么 Device 还要再分一次？

### 1. 两次规划管的不是同一批对象

前面的 Stream 阶段不是已经安排好了 buffer 吗？为什么到了这里又出现 SRAM allocator？

Stream 规划的是模型输入、输出，以及跨 dispatch 传递的资源。例如 D0 写出 H、D1 再读取 H，需要一块能跨任务存在的 buffer，并通过依赖保证读取时机。

而 D1 真正执行时，还要把数据搬进 SRAM，保存当前部分和，再给逐位重建安排 scratch。这些是一次工作组程序内部的存储问题。

[CIMMaterializeSRAM.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMMaterializeSRAM.cpp)分析 HAL binding 与非 Array 静态数据的使用，为参与计算的视图建立 SRAM staging：

```text
HAL binding / embedded data
    ↓ 必要的 memref.copy
SRAM activation / accumulator
    ↓ bit 与 elt 计算
SRAM output
    ↓ 必要的 memref.copy
output binding
```

“必要”也需要分析。如果输出会在读取前被完整覆盖，就没必要先把旧输出搬进来；若只写部分区域，或计算要读原累加值，就必须保留所需初值。这依赖视图、别名与覆盖范围，不能只看 buffer 名字。

### 2. 为什么顺序必须是“物化 → 展开 → 分配”？

当前 linking pipeline 的顺序为：

```text
Array 放置
    → SRAM staging 物化
    → bit-serial 展开，补出每个 MVM 的 scratch
    → 生命周期分析与 SRAM 地址分配
```

如果在 bit-serial 展开前分配，分配器根本看不到刚才那块 scratch。它算出的峰值自然不是最终程序所需的峰值。

[CIMAllocateSRAM.cpp](../../compiler_plugins/cim/src/cim/Codegen/CIMAllocateSRAM.cpp)要求静态、直线化的入口缓冲区，为分配设置 64 Byte 对齐，并复用 MLIR 的静态内存规划。顺序策略使用 `Trivial`；复用策略先缩短 allocation 的活跃区间，再使用 `BestFit`。

比如，第一个 MVM 的逐位重建完成后，它的 scratch 已经没有读者，后面的 MVM 就可以使用同一段地址。两个值在 IR 中不同，并不意味着一定要占两段永久独立的空间。只要沿别名追踪后的活跃区间不重叠，就有复用机会。

最终 SRAM arena 不能超过 512 KiB。与权重的常驻布局相比，这里的规划还利用了时间：不同暂存可以先后占用同一位置。

## 十、从物理程序回到一次 IREE 调用：payload、binding 和 Runtime 怎样接上？

### 1. VMFB 里装的是 ISA 文本吗？

不是。序列化器 [CIMExecutablePayload.cpp](../../compiler_plugins/cim/src/cim/Target/CIMExecutablePayload.cpp)从同一份物理程序生成两种产物：

```text
物理 CIM 程序
    ├── CimExecutable 数值 payload → hal.executable.binary → VMFB
    └── .cim.isa 文本
```

运行时读取 payload。ISA 文本保留相同的操作顺序、阵列范围与 SRAM 地址，便于阅读。内层 payload 是自定义的 CIMX v2 记录格式，外层 VMFB 则保存 Host 字节码和内嵌设备载荷。

payload 的 export 表指定每个入口的程序区间，view 表描述操作数，program 表保存有序操作，data 区保存静态数据。到此处，逻辑 MVM 已全部展开，不能再把循环和物理决策交给 loader 临时猜测。

| 最终物理操作 | payload 记录 | 做什么？ |
| --- | --- | --- |
| `memref.copy` | `TRANSFER` | 搬运 boundary、静态数据和 SRAM 视图之间的数据 |
| `cim.array.load` | `ARRAY_LOAD` | 部署静态权重 |
| `cim.bit` | `BIT` | 执行 activation 某一位对应的 MVM |
| `cim.elt` | `ELT` | 执行向量加减乘除与立即数操作 |

序列化器会拒绝未展开的逻辑 CIM 操作和带嵌套 region 的程序操作。它的工作是编码已经确定的物理程序。

### 2. 一份程序怎样处理两个 workgroup？

还记得案例被分成两组，每组覆盖 8 行吗？如果 payload 只保存一份程序，第二组怎么找到后 8 行？

view 的地址保留了 workgroup ID 的线性关系：

\[
\mathrm{offset}=\mathrm{base}+c_x\,wg_x+c_y\,wg_y+c_z\,wg_z.
\]

因此，案例中第 g 组的起始偏移是：

```text
X：g × 8 × 32 × 1 Byte = g × 256 Byte
Y：g × 8 × 64 × 4 Byte = g × 2048 Byte
```

组内行切片再增加自己的常量偏移，HAL subspan 原有的字节偏移也会计入。第二组使用同一份运算，只把数据窗口平移到下一组输入和输出。

运行时则根据 view 的类别选择根地址：

| 存储类别 | 地址从哪里来？ |
| --- | --- |
| `binding` | Host 为本次 dispatch 提供的 `binding_ptrs[ordinal]` |
| `embedded_data` | payload 的静态数据区 |
| `array` | executable 实例保存的 Array 状态 |
| `sram` | 当前工作组的 `local_memory` |

这里与 GPU 案例中的局部 binding 和 Host slot 是同一种接口思路：Host 提供实际 buffer，Device 程序保存相对地址与访问方式。区别在于，CIM 程序还要访问自己规划的 Array 和 SRAM。

当前 payload 接受 rank-1/2 的静态 i8/i16/i32 视图、静态 stride，以及可编码的非负 32-bit 地址字段。要支持更一般的动态寻址，还需要相应 lowering 和载荷格式。

### 3. 当前实现真的在驱动 CIM 芯片吗？

这里需要把“编译完成了什么”和“在哪里执行”分开。

[driver.c](../../compiler_plugins/cim/runtime/driver.c)注册 `cim` 驱动工厂，加入自定义 executable loader，再复用 IREE local-sync 的设备实现。buffer、命令缓冲和同步继续走原生 HAL 路径。

[cim_executable.c](../../compiler_plugins/cim/runtime/cim_executable.c)则解释 CIMX payload，创建 Array 状态，确定每个入口的 binding 与本地内存需求，并在 `issue_call` 中执行记录：

```text
Host VM 字节码
    → HAL 命令与队列提交
    → local-sync 工作组调用
    → CIM executable.issue_call
    → 用 binding 与 workgroup ID 解析 view
    → 顺序执行 TRANSFER / ARRAY_LOAD / BIT / ELT
```

当前这些操作由 C 代码在 CPU 内存中模拟数值与存储语义，能够运行模型并验证编译结果；真实 CIM 芯片的寄存器下发、DMA 和硬件队列尚未包含在这条路径中，运行耗时也不能直接当作芯片延迟。

回到最初那个 `Y=X@W`：W 先由张量常量变成逻辑权重，再被安排到固定 Array 区域；X 由 HAL binding 进入 SRAM，逐位驱动该区域；Y 经过部分和重建与回写，重新成为 Host 可以返回的输出。

而这些硬件细节并没有要求 Host 重新理解一遍矩阵乘。它依然按 IREE 生成的任务、binding 和依赖发起调用，设备 payload 则已经把每次调用内部要做的事写清楚了。
