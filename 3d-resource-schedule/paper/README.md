# DAC 中文初稿


> **写作准则与定位红线**：修改本目录下任何章节、文本与图表说明前，必须严格遵守项目专属 Skill `skill://moe-3dcim-paper-writing`。论文定位为**软硬协同的部署与执行框架**（非纯算法亦非纯工程工具流）；严禁使用浮夸辞藻与商业黑话；禁止防御性声明；客观陈述 Decode 与 Prefill 的权衡。

入口为 `paper/main.typ`，PDF 输出到 `output/pdf/dac-paper-cn.pdf`。正文按 8–9 页中文双栏工作稿组织，参考文献接续正文排版。主标题、摘要、关键词、贡献点、章/节标题、图内文字、图注和表格（含表头、单元格及表注）统一使用英文；正文及段首引导语使用中文，正文中的图表交叉引用使用“图／表”。参考文献保留英文原文，补充材料遵循相同规则。参考文献使用英文语言环境生成作者连接词、卷期页码及在线来源说明。当前使用 11 pt 中文正文、统一数学字体和七组矢量图；正式投稿阶段依据 DAC 当年模板压缩版面。

论文标题为 **A Deployment and Execution Framework for MoE Inference on 3D CIM Systems**。主线是将三维存内计算的专家驻留容量转化为动态 MoE 执行收益。英文 Introduction 保留三项技术贡献：硬件抽象与代价模型、部署与执行框架、权重映射与数据流调度算法。量化结果由摘要与实验章报告。技术内容保留硬件抽象、权重映射、数据流调度和性能分析四个部分。中文稿暂缓同步。

正文按 Introduction、Background and Motivation、Hardware Abstraction、Inference Framework、Evaluation 五章组织。硬件接口提供几何与时间描述；离线阶段构造驻留集合，在线阶段选择执行副本与规约根。背景从固定布局下的绑定和汇聚位置示例接到副本空间占用、算子时间与后继层输入位置，第三章解释硬件组织和时序，第四章沿编译产物、部署选择、执行评价及反馈展开。Inference Framework 按 Overview、Framework Design、Algorithms 组织；映射与调度正文分别由 `mapping.typ`、`scheduling.typ` 持有。轨迹内交换与跨轨迹验证门限分别说明参照对象；跨轨迹验证保留最小可行最大回退规则。相关工作和结论分别由背景与实验末段承载。

中文行文参照 [PIMCOMP（DAC 2023）](https://doi.org/10.1109/DAC56929.2023.10247928) §III-B、§IV-C 中共享资源、执行规则与联合选择的递进，以及 [CIMFlow（DAC 2025）](https://doi.org/10.1109/DAC63849.2025.11133270) §III-A、§III-C 中输入、编译产物、代价评价与决策之间的承接。以完整自然段的句子作用和对象传递为参照，中文正文继续使用本项目的节点组织与 FFN 执行范围。

实验章进一步参照 PIMCOMP §V-B 的固定计算工作量、瓶颈转移与代价解释，以及 CIMFlow §IV-B/C 的受控编译比较与硬件参数权衡。Gemini 主笔实验段落，合作者围绕实际数据、比较分母与图面证据讨论取舍；正文围绕位置、串行、通信和节点工作量组织论证。


英文实验保留一组总体／预算结果与两组机制图。图 4／5 给出正式收益及预算曲线，图 6 解释副本预算对两阶段物理时间的不同作用；图 7 固定 20% 部署，检验运行时怎样使用已有执行位置。正文按 Prefill／Decode 的解释依赖组织，具体论证职责见[写作框架第五章](PAPER_WRITING_FRAMEWORK.md#5-evaluation)。

Experimental Setup 交代 FFN 范围、路由来源与划分，以及容量、额外副本预算和指标口径。结果按各自基准归一化，正文用平均节点计算时间下界、执行残差与关键路径分量解释预算收益，冻结部署的策略对照分别接入两阶段。逐配置结果由图表承载。

## 构建

服务器重跑矩阵、数据口径和更新顺序见仓库根目录 [`HANDOFF.md`](../HANDOFF.md)。
主实验搜索 0%–20%，三模型比较使用 20% 终点。`experiments.paper_run collect` 生成主结果 `paper/data/results-20pct.json` 和 `artifacts/results/cross-model-20pct.json`。图 6、图 7 的新机制数据由 `experiments.paper_mechanisms` 单独生成 `paper/data/mechanisms.json`，读取同一批冻结部署与 seed0 输入。

在仓库根目录执行：

```sh
typst compile paper/main.typ output/pdf/dac-paper-cn.pdf --root . --font-path assets/fonts
```

先重放机制实验，再生成四张论文数据图（macOS 示例，worker 上限 8）：

```sh
conda run -n npu env PYTHONPATH=.:python NPU_WORKERS=8 python -m experiments.paper_mechanisms
conda run -n npu python paper/figures/build_figures.py --data-only
```

机制重放包括 Planar/Vertical × 三档映射带宽 × 三档评价带宽的 18 个单副本测试点、六组冻结 20% 部署的调度比较、八个 20% 端点交叉重放点，以及 Planar 2 GB/s、T128 首测试窗口的两种 Prefill 原始时间线。Decode 使用 4,096 条 Test 路由，Prefill 汇总每规模八个窗口；原始计算区间与分组报告保存在 `build/paper-mechanisms/`。Linux 默认 worker 为 32。

主图沿用 Libertinus；机制图使用嵌入式 STIXGeneral TrueType 字体。图 1–3 继续使用已提交的矢量文件。

三张架构图以 `figures/01-framework.drawio`、`02-hardware.drawio`、`03-mapping-scheduling.drawio` 为权威可编辑源文件。`figures/build_figures.py` 统一导出嵌入 XML 的 `.drawio.pdf`、`.drawio.svg`、`.drawio.png`，构建使用 `/Applications/draw.io.app/Contents/MacOS/draw.io`。实验图由 Matplotlib 读取主结果与机制数据并生成 PDF/PNG，色值与字号保存在同一构建脚本。

架构图采用工程线图风格，参考 PIMCOMP Fig. 2–3、DAC 2025 Efficient Weight Mapping Fig. 3、CIM-MLC Fig. 3–4 和 UpDLRM Fig. 4 的层级与数据流组织。图 2 采用核心—路由器分离的 Mesh：蓝色核心通过本地连接接入浅金色路由器，双向链路连接路由器；虚线框标出被展开的完整节点。节点内显示控制、输入分发、二维 Unit-Cube 阵列、部分和规约与输出缓冲。

图 2 右上将 Unit-Cube 展开为多层阵列与共享行驱动、列读出；输入输出宽度和存储深度分别标为 `hᵤ`、`wᵤ`、`Dₛ`。右下把 Planar 的多个局部读出与 Vertical 的单元内深度累加并排对照，计算深度标为 `d`，ADC 后的数字结果用蓝色连线标识。图 3 以硬件接口、离线部署、在线调度和共享执行评价组织框架，展开双轨初始化、复制与位置交换、部署选择以及 Decode／Prefill 两类决策。图形用于解释具体对象和操作，标签直接说明功能和关系。黑灰描边和 Arial 标签承担结构说明；正式排版引用矢量 PDF，PNG 预览按两倍尺寸导出。`figures/concepts/` 保存早期视觉探索。

调度对照表由 `sections/scheduling.typ` 持有，表题为 `Dataflow Scheduling Policies`。Decode 的副本与规约根联合选择使用跨行单元格；Prefill 并列展示最小累计工作量分派与最少树边规则。通信树、任务优先级与链路可用时间作为共同规则跨列合并，具体语义由相邻正文说明。

### 英文前五章（DAC 2027）

英文入口为 [`english/dac-paper-en.tex`](english/dac-paper-en.tex)，正文、表格与参考文献源文件独立位于 `english/`，输出为 [`../output/pdf/dac-paper-en.pdf`](../output/pdf/dac-paper-en.pdf)，中间文件位于 `build/paper-english/`。英文稿包含摘要及 Introduction、Background and Motivation、Hardware Abstraction and Cost Model、Inference Framework、Evaluation 五章，当前为 6 页正文加 1 页参考文献，中文工作稿为 9 页。当前英文摘要由英文入口持有；中文稿保留 `main.typ` 中的版本并暂缓同步。中英文分别维护实验正文和图注，共享图 6、图 7 的数据图。主实验数据与图 4、图 5 沿用原正式批次。

**冻结文本**：当前冻结范围为英文摘要与三项技术贡献，以英文源为准。本轮按用户明确授权删除重复报告性能结果的原第四条贡献，前三条原文及顺序完整保留。摘要中的量化结果保持原样，第五章继续提供实验依据；后续篇幅、叙事及图表调整保持当前冻结文本。

英文稿统一以 `replica` 指专家权重的驻留实例，复制操作使用 `replication`，计数包含初始实例。算子执行时间使用 `operator execution time`，专家执行时间使用 `expert execution time`；首次定义明确节点内范围，完整执行模型评价 Mesh 传输与节点、链路争用。`cumulative assigned compute time` 表示调度器累计分配的计算时间。激活位宽使用 `b_act`，副本绑定使用 `a`。权重复制增加其他节点上的相同权重实例，结构重排对应专家权重的空间布局变化；固定布局上的副本绑定和规约根选择属于运行时决策。

英文前两章由 Gemini Argon 主笔，合作者共同讨论章节职责、术语与物理含义。引言先说明片上权重存储，再以最低必要信息引入空间布局和权重复制，保持共同部署下的 Decode／Prefill 取舍。第二章的文献比较分别支撑统一硬件模型和部署、执行评价框架，随后以三个短段建立权重映射、Decode 联合选择及 Prefill 节点工作量分派的动机。图 1 保留共享权重布局和两种 Decode 执行，时延差归于固定部署上的运行时选择。双方参照 DAC 原文的物理约束与设计需求承接方式；操作对象在首次出现或存在歧义处写明，引言继续直接使用 decode／prefill。

英文前两章按 [DAC 全文结构研究](DAC_PAPER_WRITING_STUDY.md) 的统一口径统计：Introduction 为五个自然段与三项技术贡献，共 408 词；Background and Motivation 为两个小节、七个自然段，共 423 词，两章合计 831 词。2.1 `3D CIM and MoE` 共 116 词；2.2 两个相关工作短段之后，映射、Decode 示例及 Prefill 动机分别为 47／97／43 词。图 1 为 440×270 的单栏图源，一幅共享 Mesh 与两条时间轴表示同一部署；生产仿真及独立分支时间计算均得到最近副本／源根 $6\tau$、联合副本与规约根选择 $4\tau$。英文已重编译并逐页检查正文，保持 6 页正文与 1 页参考文献，无 overfull 或未定义引用，仍有 underfull 提示。引言、摘要与三项贡献、其余英文章节、表格、中文源文件及实验数据保持原样。

第三章英文源为 [`english/sections/hardware.tex`](english/sections/hardware.tex)，按以下框架展开：

- **Architecture Model**：自底向上定义 Unit-Cube、Sub-Cube、Node 与 Mesh，说明各层参数对切片、存储边界和执行资源的作用；以统一硬件配置提供几何及时间参数。
- **Weight-Cube Representation**：先说明全算子长度 `K_o,M_o`、融合 gate/up 与 down 的存储列数 `C_w`，再定义描述符、输入切片与深度 `d`。以层内展开和跨层累加分别描述 Planar 与 Vertical；几何描述之后由执行时间模型给出 `d` 的选择准则。平面分片数为 `F_c=F_H F_W`，分片逻辑长度向上取整；随后给出 `D_c=F_c d`、平面对齐及非重叠约束。
- **Operator Execution Time**：函数以 section 长度 `K,M` 为输入。Planar 从首次发射与剩余发射间隔推导流水跨度，Vertical 区分并行组与组内顺序步骤；深度选择先评价全算子输入的深度相关项，再形成 sections 并累计块及专家时间。时序标定保留源映射、尾部等分及 3D-FPIM 事件计数口径。
- **Network Transfer Time**：区分包级单跳服务时间、资源可用时间和最终完成时间；最短路径多播/规约树明确属于本次采用的执行策略。

第四章英文源为 [`english/sections/methodology.tex`](english/sections/methodology.tex)，按 Overview → Framework Design → Algorithms 展开，总览对应图 3(a)–(d)。部署 `X` 暴露驻留集合 `R_e`，规划器以无争用分支评分 `L` 比较绑定与规约根，模拟器根据链路释放时间和规约依赖得到完整 `J_D`。时延分解覆盖 Dense 与 MoE FFN，`T_wait` 为完整时延残差；图中 `Serial` 对应 `T_node`。每次正向 FM 扫描前，映射器反向计算所有采样轨迹与候选输入节点的后缀表，候选移动更新当前层并查询新根处的后继值。Prefill 分派累计已分配计算时间并逐专家更新，再按树边数与返回跳数选择规约根。同轨迹交换门限比较副本追加候选；跨轨迹验证门限比较同预算、各批大小上的最佳候选时间。两级门限均为 2%；跨轨迹验证在两者均未通过时采用最小可行最大回退门限。

第五章英文源为 [`english/sections/evaluation.tex`](english/sections/evaluation.tex)，范围为 Dense/MoE FFN 执行链。优化、验证与测试使用分离的 4,096-token 轨迹块，Prefill 各规模使用一个验证窗口和八个测试窗口。复制预算包含 routed/shared 驻留单元，Qwen2 的共享 FFN 按八个与路由专家等宽的单元表示。主基准按 Dense/MoE 工作构造单副本均衡布局，并沿用相同运行时策略；主图速度／吞吐为基准与候选平均时延之比。预算曲线使用 Validation，跨模型、单副本位置重放与冻结部署调度使用 Test。图 6 矩阵按匹配布局归一化，空间图按每路由每 MoE 层统计同节点超出一份的活跃专家及树流量。图 7 的网络与串行变化按就近副本＋输入源规约的平均总时延归一化，Prefill 时间线与节点工作量对比轮转和累计工作量分派。


版式依据 [DAC 2027 官方投稿规则](https://dac.com/2027/program/research-manuscript-submissions) 与 [IEEE 官方会议模板](https://www.overleaf.com/latex/templates/ieee-conference-template/grfzhhncsfqn)：使用原版 `IEEEtran` conference 类、US Letter、10 pt、双栏和匿名 PDF 元数据，保留空白作者区，参考文献另起一页。正文上限为 6 页，参考文献限 1 页。类文件控制页边距、栏宽、行距与标题样式；T1 字体编码用于在 Tectonic 下保持 IEEE 默认 Times 正文字体。

构建依赖 Tectonic、draw.io Desktop 和 Ghostscript；从仓库根目录执行：

```sh
make -C paper/english TECTONIC="$HOME/.local/bin/tectonic"
```

`TECTONIC` 默认使用 PATH 中的 `tectonic`。当前本机编译器位于 `~/.local/bin/tectonic`，首次编译会下载 IEEE 类、参考文献样式和字体资源。`DRAWIO` 默认使用 `/Applications/draw.io.app/Contents/MacOS/draw.io`。英文参考文献独立保护论文名称及缩写的大小写，出版字段依据原始论文及正式元数据补齐，并保留预印本与数据集 URL。

英文执行示例的权威可编辑源为 [`english/figures/motivation.drawio`](english/figures/motivation.drawio)，预览为 [`english/figures/motivation.drawio.png`](english/figures/motivation.drawio.png)。两个面板保持相同权重驻留位置，通过实色与灰色区分选中和未选中的副本；`S` 标识输入源，`R` 标识规约根及下一层输入源。时间线使用圆点标输入到达、色块标专家计算、虚线箭头标结果转发；目的节点文字独立置于箭头上方。竖线与就绪标签共同标出层完成时刻，单独调整副本或规约根的对照结果由正文持有。专家下标使用原生字符排版，并为标签保留完整高度。

英文硬件图的独立可编辑源为 [`english/figures/hardware.drawio`](english/figures/hardware.drawio)，预览为 [`english/figures/hardware.drawio.png`](english/figures/hardware.drawio.png)。该图沿用现有四级硬件图的结构，并将微元驻留层数标为 `D_u`，与节点容量深度 `D_s` 区分。两版独立图源的 Planar 均以 `U₀`、`Uₖ` 和微元／ADC 两行水平省略号表示多个读出分支。

构建分别由 draw.io 导出含可编辑 XML 的 `build/paper-english/{motivation,hardware,framework}.drawio.pdf`，再由 Ghostscript 将图中文字转为矢量轮廓，生成 LaTeX 引用的同名 PDF。框架图独立源为 [`english/figures/framework.drawio`](english/figures/framework.drawio)，预览为 [`english/figures/framework.drawio.png`](english/figures/framework.drawio.png)。图 3 的双栏浮动声明在 `sections/hardware.tex` 的标定段前预置，使其位于第四章开头附近；模块解释由第四章 Overview 持有。图内时间、平均 Decode 时延和资源界差标签与正文对应。实验图复用 `figures/04-main-results.pdf` 至 `07-cross-model-results.pdf`，英文构建生成独立轮廓版本；共享源与中文构建产物保持独立。

### 硬件原型对照表设计样稿

独立入口为 [`english/hardware-prototypes.tex`](english/hardware-prototypes.tex)，表格源为 [`english/tables/hardware-prototypes.tex`](english/tables/hardware-prototypes.tex)。同一表源由英文第三章和独立样稿共同引用，按 IEEE 单栏宽度排版，使用 9 pt 表文、四列和五个代表性设计；独立样稿输出 [`../output/pdf/hardware-prototypes.pdf`](../output/pdf/hardware-prototypes.pdf) 与 PNG 预览。本轮以英文表格为准，中文稿暂不更新。

```sh
make -C paper/english hardware-preview TECTONIC="$HOME/.local/bin/tectonic"
```

预览图导出额外依赖 Poppler 的 `pdftoppm`。主表沿用设计报告选定的 ICCD 2025、Nature 3D AIMC、3D-FPIM、Sharma 异构 SRAM/ReRAM 系统和 NASiC 五篇，四列分别为 Design、Readout、Unit-Cube 和 Native macro。后两列均保留完整三维几何，对照计算微元与原文宏组织；模型的逻辑节点容量、网格规模和时间参数由硬件配置单独给出。Sharma 的几何来自面积模型。NASiC 按原文 Table I 的 1k SL、128k BL、128 WL 配置列出宏几何；Unit-Cube 取 128-input 参考点，以输出编码和 CAM 层占用表达可用几何。数值时序标定继续使用 Jang 与 3D-FPIM 两个参考。

第四列沿用设计报告“原文系统宏”的层级职责。NASiC 条目取原文 NAND plane：按 [Table I](https://arxiv.org/html/2605.23294#S3.F1) 的 SLs × BLs × WLs 直接计数，英文表为 $1024\times131072\times128$；报告旧行的 162 层与该评价配置不同。CAM 预留层通过 Unit-Cube 的 $D_u=128-D_{\mathrm{CAM}}$ 单独表达。

## 当前数据入口

主实验数据为 `data/results-20pct.json` 和 `artifacts/results/cross-model-20pct.json`，源批次 `build/dac-paper-full-workload/`。三模型使用 2 GB/s、约 20% 额外副本，DSV3 深度 460、DSV2-Lite 11、Qwen2 39。`resource_diagnostics.planar_budget_curves` 保存正式 `diagnostics.json` 中 0%／约 5%／约 20% 的九个 Planar 验证样本，用于英文容量机制图，原实验数值保持。`data/mechanisms.json` 保存 DSV3 seed0 机制重放及原始计算区间。公开／合成来源及阶段划分见 [根目录交接](../HANDOFF.md)，主实验新旧比较见 [RUN_REPORT](../build/dac-paper-full-workload/RUN_REPORT.md)。

| 正文图号 | 文件基名 | 数据 |
| --- | --- | --- |
| 4 | `07-cross-model-results` | 三模型 20% Test，单栏 |
| 5 | `04-main-results` | DSV3 0%–20% Validation，四行三列，Decode＋T32/T128/T512 |
| 6（英文） | `05-capacity-mechanisms` | Planar 验证预算诊断；Prefill 固定平均工作以上的时间与 Decode 可变关键路径 |
| 7 | `06-scheduling-results` | 冻结 20% Test；Decode 成本交换与 Prefill 节点时间线／工作量 |

主结果以全工作量均衡单副本布局为基线，P/V 色条标识入选轨迹。英文图 6(a) 的三个分量相加为 $J_P-\bar W$：计算峰均差、链路峰值高于计算峰值的部分，以及超出峰值资源时间的执行余量；$\bar W$ 为平均节点计算工作。图 6(b) 去除固定专家计算，并以同带宽 0% 入选部署总时延归一化。原单副本跨带宽矩阵和 Mesh 图 `05-decode-analysis` 保留给暂停同步的中文稿。图 7(a) 的原点为最近副本＋源节点规约，箭头从动态根到联合规划，网络包含传输与等待；图 7(b) 共用绝对时间轴，斜线表示窗口已完成，侧条按平均节点工作量归一化。

`data/results.json`、5%/10% 图和旧批次保留各自历史身份，当前构建读取主实验的两份 20% 汇总及独立机制数据。机制重放核验包括显式就近副本与 16 根枚举、全 Test 空间统计的独立向量化重建、节点区间互斥及占用积分守恒。实验与写作交接见 [Codex–Gemini 交接](CODEX_GEMINI_HANDOFF.md)。

## 当前稿图组

1. 动机例子：单栏比较 Mesh 局部区域中的副本绑定、规约路径和节点时间线。
2. 硬件架构：Mesh → Node → Sub-Cube → Unit-Cube 的层级展开，以及 Planar／Vertical 执行方式和权重块接口。
3. 软件架构：Weight-Cube 字段定义硬件接口；计算均衡与状态感知超图构造双轨起点；逐预算交织 Prefill 复制与 Decode 细化，经回放选择部署；同一部署进入 Decode 联合选择或 Prefill 累计工作量分派。共享模型呈现节点串行、链路排队和层间依赖，并输出 Decode 时延分解与 Prefill 资源负载。虚线表示预算推进和时延反馈。
4. 三模型总体结果：单栏，上下两个面板分别展示 Planar／Vertical 的约 20% 预算冻结测试改善。
5. 预算曲线：4 行 × 3 列，列对应 0.5/2/8 GB/s，行对应 Decode、Prefill T32/T128/T512。
6. 英文容量机制：前段副本消除 Prefill 热点，后段预算继续调整 Decode 路径；原位置敏感性图保留给中文稿。
7. 冻结 20% 部署的运行时机制：Decode 网络—串行成本坐标与 Prefill 真实计算占用。

图组采用深蓝、中蓝、浅蓝、灰色及少量金色。英文图 4 为 3.36 × 1.85 inch，图 6、图 7 为 7.05 × 1.75 inch；图 5 保持原尺寸。本轮仅修改英文实验正文及图注，图像、实验数据、绘图代码与前四章保持原样。按用户决定删除正文中的跨带宽重放段，保留原数据与历史图源；现行实验安排以写作框架第五章为准。中文及设计报告继续保持原样。

正文保留权重块接口、超图目标、后缀价值、交织流程、在线选择与性能投影的关键关系。硬件标定、取整、装箱实现、搜索前缀和仲裁细则由补充材料 A–D 承接，扩展实验由 E 承接。

中文与英文参考文献分别由 `references.bib` 和 `english/references.bib` 维护，按各自正文引用编号，覆盖 MoE 模型、三维存算、存算编译、跨层专家亲和、性能建模和 FM 搜索。正文仅在 Introduction 末尾统一提及一次补充材料，中文稿末尾保留 AI 辅助生成披露。中文实验段落连续排版，参考文献接续正文；英文参考文献独占末页。

## 补充材料

`supplement.typ` 将五章正文的补充内容整理为一份独立中文文档，输出为 `output/pdf/dac-supplement-cn.pdf`。首页给出正文对应位置与保留项，正文内容包括硬件服务时间推导、空间编译、增量搜索及决策细节、性能投影推导和当前批次的扩展结果。

```sh
typst compile paper/supplement.typ output/pdf/dac-supplement-cn.pdf --root . --font-path assets/fonts
```

材料来源：A 部分取自 `report/appendices/hardware-cost.typ`，并按 `python/deployment/cost_primitives.py`、`costs.py` 补齐位宽到字节数的换算及整数取整；B/C 部分核对空间编译、装箱、超图搜索和候选选择实现；D 部分核对 `python/profiler/metrics/prefill.py` 中的逐窗口资源界、依赖界和汇总规则。

跨模型表直接读取 `artifacts/results/cross-model-20pct.json` 的测试值；20% 预算表直接读取 `paper/data/results-20pct.json`，与正文共用计算均衡单副本基准和验证划分。历史递进／直接构造对照保存在设计报告，当前论文补充材料使用本批数据。

本批选入与正文四块技术内容直接对应的推导和证据。QKVO 映射范围扩展、独立模范映射及历史求解分支继续由原设计报告和研究记录保存。
