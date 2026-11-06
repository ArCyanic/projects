// 第 4 章 程序运行效果与实验结果

= 程序运行效果与实验结果
<ch4-程序运行效果与实验结果>

== 实验测试基准
<sec4-1-实验测试基准>

为了全面评估存算一体编译体系在功能正确性、图级拓扑变换、两级平铺合法化以及底层资源管理方面的实际表现，本项目构建了覆盖开发构建、模型导入、执行仿真与数值校验的完整实验环境。测试软硬件环境配置如 @tbl-exp-environment 所示。

#figure(
  align(center)[#table(
    columns: (25%, 75%),
    align: (x, y) => if y == 0 { center + horizon } else { (center + horizon, left + horizon).at(x) },
    table.header([环境类别], [配置版本与组件描述],),
    table.hline(),
    [通用宿主平台], [Linux (x86_64 / aarch64) 或 macOS (Apple Silicon)，推荐 16 GiB+ 内存],
    [系统构建工具链], [支持 C++17 的 GCC 或 Clang，CMake 3.26+，Ninja],
    [IREE 编译运行时], [仓库 `iree` 子模块源码构建，静态集成 CIM 编译器插件与外部 CIM HAL 驱动],
    [模型导入与验证], [Python 3.14，依赖版本以仓库 `requirements.txt` 为准],
  )],
  caption: [实验软硬件运行环境与工具链配置],
  kind: table,
) <tbl-exp-environment>

在评估测试集设计上，测试套件涵盖三类典型基准：第一类为官方赛题整型模型，用于检验从 ONNX 规范化接入到目标代码生成的全流程连通性；第二类为*综合优化用例*（Integrated Showcase），在单一程序中构造共享激活、异构激活与多行权重复用三条独立分支，评估图级优化与 SRAM 复用的组合效果；第三类为*二维合法化用例*（2D Legalization），分别构造超出物理阵列列容量（$N > 512$）与行容量（$K > 1024$）的大尺寸矩阵乘，检验两级平铺、部分和累加与单阵列全局放置的正确性。

为了量化评估芯片侧的工作负载与资源开销，系统从编译生成的物理 CIM IR、文本 ISA 指令集以及 VMFB 二进制载荷中直接提取结构化统计指标，如 @tbl-metric-definitions 所示。

#figure(
  align(center)[#table(
    columns: (22%, 78%),
    align: (x, y) => if y == 0 { center + horizon } else { (center + horizon, left + horizon).at(x) },
    table.header([评估指标], [形式化度量标准与物理含义],),
    table.hline(),
    [权重区域数], [初始化入口 `__cim_array_init` 中调用的 `cim.array.load` 离散区域总数],
    [阵列占用单元], [全模型所有部署静态权重矩形 $k_i times n_i$ 面积之和（含块对角结构零）],
    [MVM 执行窗口], [位编号为 0 的 `cim.bit` 算子总数，计数各入口工作组程序中的 MVM（不乘 grid）],
    [位计算轮次], [各入口工作组程序内的 `cim.bit` 算子总数（不乘 grid），衡量程序内的位计算工作量],
    [SRAM 峰值地址], [全模型生命周期中局部缓冲区所达到的最大绝对物理地址 $max (o_i + s_i)$],
    [二进制载荷大小], [嵌入 VMFB 容器内部的 `hal.executable.binary` 专有字节码总字节数],
  )],
  caption: [系统结构化评估指标定义与度量含义],
  kind: table,
) <tbl-metric-definitions>

== 数值一致性验证
<sec4-2-数值一致性验证>

编译器的首要前提是保证端到端计算结果在数值层面的绝对正确性。为此，实验构建了双轨对齐的数值验证流水线，如 @fig-numeric-verification-paths 所示。

#figure(
  image("assets/numeric-verification-paths.pdf", width: 92%, alt: "CIM 编译执行路径与 ONNX Runtime 参考验证路径"),
  caption: [CIM 编译执行路径与 ONNX Runtime 参考验证路径],
) <fig-numeric-verification-paths>

整个验证流程在双轨结构下同步展开。在参考验证路径中，原始 ONNX 模型经过赛题规范化解析后，转换为符合标准规范的计算图，由工业级参考推理引擎 ONNX Runtime 解释执行以产生基准输出；在 CIM 编译执行路径中，输入相同的原始 ONNX 模型，通过本项目研发的端到端编译器完成算子规范化、异构融合、两级平铺降级、单阵列静态放置、位串行展开与 SRAM 活跃期分配，生成单一的 VMFB 可执行文件，随后通过自研的外部 CIM HAL 运行时驱动在 CPU 宿主环境下模拟执行专有存算指令并捕获最终输出。

官方模型与自建用例的 VMFB 输出均与 ONNX Runtime 参考结果逐位一致。

== 综合优化消融分析
<sec4-3-综合优化消融分析>

为了剖析各项图级重排优化与片上内存复用算法对系统性能与资源开销的独立贡献，实验在综合测试用例上实施了渐进式消融实验。测试用例在同一程序中同时容纳了共享输入特征、异构分支计算以及多行共享权重三种典型结构，各阶段累计优化数据记录于 @tbl-ablation-results。

#figure(
  align(center)[#table(
    columns: (24%, 10%, 15%, 13%, 12%, 12%, 14%),
    align: (x, y) => if y == 0 { center + horizon } else { (left + horizon, center + horizon, right + horizon, right + horizon, center + horizon, center + horizon, right + horizon).at(x) },
    table.header([编译配置方案], [权重区域], [阵列占用 (单元)], [载荷大小 (B)], [MVM 窗口], [位计算轮次], [SRAM 峰值 (B)],),
    table.hline(),
    [基线 (Baseline)], [9], [81,920], [128,197], [24], [384], [12,288],
    [\+ 横向列拼接], [6], [81,920], [118,533], [12], [288], [16,384],
    [\+ 异构块对角融合], [5], [86,016], [118,968], [11], [256], [16,384],
    [\+ 多行权重复用], [5], [147,456], [170,520], [8], [160], [16,384],
    [\+ SRAM 活跃期复用], [5], [147,456], [170,520], [8], [160], [10,240],
  )],
  caption: [综合优化用例的渐进式累计消融实验结果],
  kind: table,
) <tbl-ablation-results>

IREE 原生横向融合保留 $M<16$ 不融合的限制，因此综合用例中的两个 $M=1$ producer 分别执行。根据 @tbl-ablation-results 的数据，各阶段的收益与代价如下。

在启用*横向列拼接*后，同一 Dispatch 内共享激活的矩阵乘沿输出列合并。综合用例的总执行窗口由 24 降至 12，位计算轮次由 384 轮降至 288 轮，阵列占用保持 81,920 单元。非连续目的缓冲通过 `memref.copy` 写回，拼接结果与原缓冲同时存活，SRAM 峰值由 12,288 字节升至 16,384 字节。独立的 `resource_showcase` 上，该变换将窗口由 16 个减为 4 个。

在叠加*异构块对角融合*后，互不依赖的异构矩阵乘改写为块对角收缩，总窗口降至 11，位计算轮次降至 256 轮。块对角非重叠区域填入结构零，阵列占用增至 86,016 单元。

在引入*多行权重复用*后，行尺寸较小的权重在行维复制，对应分支由多次窗口改为一次宽窗口，全模型总窗口收敛至 8 个（相对基线降幅 *66.7%*），位计算轮次降至 160 轮（降幅 *58.3%*）。阵列占用增至 147,456 单元，占用率为 $28.12\%$。

最后启用基于 Liveness 的 *SRAM 活跃期复用*。计算轮次与权重布局不变，互不重叠的中间张量共用地址，SRAM 峰值由 16,384 字节降至 10,240 字节（降幅 *37.5%*）；相对未优化基线 12,288 字节，降幅为 *16.7%*。

@fig-optimization-evidence 直观展示了上述累计演进趋势与单变量控制实验的归因对比。

#figure(
  image("assets/optimization-evidence.pdf", width: 95%, alt: "综合优化用例的累计归一化变化曲线与四项单变量消融归因分析"),
  caption: [综合优化用例的累计归一化变化曲线与四项单变量消融归因分析],
) <fig-optimization-evidence>

== 单阵列共存验证
<sec4-4-单阵列共存验证>

为了验证编译器在处理超大尺寸张量时的两级平铺降级与全局单阵列放置能力，实验构建了包含 $N$ 维超限（$[128, 768]$）与 $K$ 维超限（$[1536, 64]$）的二维合法化用例。两级平铺推导出的分块切分与结果重组方案如 @tbl-legalization-results 所示。

#figure(
  align(center)[#table(
    columns: (20%, 20%, 25%, 35%),
    align: (x, y) => if y == 0 { center + horizon } else { (center + horizon, center + horizon, center + horizon, left + horizon).at(x) },
    table.header([逻辑权重尺寸 $[K, N]$], [超限切分轴向], [均匀分块切分结果], [运行期数据重组与合并机制],),
    table.hline(),
    [`[128, 768]`], [$N$ 轴 / 输出列], [`[128, 384]` $times 2$], [直接原位写入连续输出通道区间，无累加开销],
    [`[1536, 64]`], [$K$ 轴 / 输入行], [`[768, 64]` $times 2$], [在局部 SRAM 累加器中通过 `cim.elt add` 显式相加],
  )],
  caption: [二维合法化用例的平铺分块与运行期结果重组机制],
  kind: table,
) <tbl-legalization-results>

实验表明，列切分算子通过改变目的视图直接原位拼装，而行切分算子通过 `cim.elt add` 在片上 SRAM 中串行累加中间部分和。四个切分子矩阵共占用 196,608 个权重单元（阵列占用率 $37.50\%$），通过面积降序、逐行寻找最左空位的放置算法成功在唯一的 $1024 times 512$ 物理阵列中实现紧凑无重叠共存，最终输出结果与 ONNX Runtime 保持逐位一致。

== 系统复现指南
<sec4-5-系统复现指南>

本项目全部代码与实验套件可在通用 Linux 与 macOS 上从源码复现。构建与中间 IR 导出以仓库根目录 README 为准，核心步骤如下：

```bash
git submodule update --init --recursive
python3 -m pip install -r requirements.txt

cmake -S iree -B iree-build -G Ninja -C cmake/cim.cmake
cmake --build iree-build --target iree-compile iree-run-module iree-opt -j8

python3 -m pytest -q

python3 tools/cim-compile onnx/int8_linear_add.onnx \
  --emit-dir output/cim-int8-linear-add --emit-stages

python3 tools/cim-showcase --output-dir output/cim-showcase
```

`--emit-stages` 一次编译同时写出 IREE 的 12 个 phase 与 CIM 链接后物理化各阶段；`cim-showcase` 按边打印 MVM 窗口、位计算轮次与 SRAM 峰值。数值测试将五个官方模型与六个 showcase 的 VMFB 输出与 ONNX Runtime 做逐位比较。
