# DAC 论文全文结构、篇幅与段落职责研究

更新日期：2026-11-01。研究范围为 PIMCOMP、CIMFlow 和 UpDLRM 的全部编号正文，并对照本项目当前英文前五章。文档按章节规模、小节组织与逐段职责展开；原来的逐轮改稿记录由当前可复算统计替代。论文源稿、图形和实验数据保持原样。

阅读入口：章节规模（第 2 节）、参考论文分析（第 3–5 节）、组织方式（第 6 节）和本稿对照（第 7 节）；核验记录见第 8 节。

## 1. 原文与版本

### 1.1 固定论文与版本

| 论文 | 固定版本及原文 | Zotero 条目／附件 key | 研究对象 |
| --- | --- | --- | --- |
| PIMCOMP: A Universal Compilation Framework for Crossbar-based PIM DNN Accelerators | [DAC 2023 DOI](https://doi.org/10.1109/DAC56929.2023.10247928)；[作者 v1](https://arxiv.org/html/2307.01475v1) | `9C23TIYU`／`9UMNUBLQ` | 抽象架构、编译、两种流水模式及其评价。 |
| CIMFlow: An Integrated Framework for Systematic Design and Evaluation of Digital CIM Architectures | [作者 v1](https://arxiv.org/html/2505.01107v1)；[接收信息](https://arxiv.org/abs/2505.01107) | `VVVGQZVX`／`LKSWCDRA` | ISA、两级编译与模拟的集成及设计空间研究。 |
| UpDLRM: Accelerating Personalized Recommendation using Real-World PIM Architecture | [DAC 2024 DOI](https://doi.org/10.1145/3649329.3658266)；[作者 v2](https://arxiv.org/html/2406.13941v2) | `PADJV4JM`／`QD97E57R` | 真实 DPU 条件下的三级分区与系统评价。 |

PIMCOMP 采用会议论文版本。其 TCAD 扩展版单独保留版本身份。三篇本地 PDF 的正文缓存分别位于 `~/Zotero/storage/{9UMNUBLQ,LKSWCDRA,QD97E57R}/.zotero-ft-cache`。

## 2. 全文章节规模

### 2.1 章节词数与占比对照

按原章号对齐，单元格为词数（占本篇正文比例）。

| 原章号 | PIMCOMP | CIMFlow | UpDLRM | 本稿前五章 |
| --- | ---: | ---: | ---: | ---: |
| I | 436（11.4%） | 541（16.6%） | 723（16.9%） | 408（15.2%） |
| II | 389（10.2%） | 539（16.6%） | 676（15.8%） | 423（15.8%） |
| III | 482（12.6%） | 1448（44.5%） | 1411（33.0%） | 672（25.1%） |
| IV | 1765（46.1%） | 600（18.4%） | 1139（26.6%） | 644（24.1%） |
| V | 675（17.6%） | 126（3.9%） | 200（4.7%） | 530（19.8%） |
| VI | 83（2.2%） | — | 125（2.9%） | — |
| 合计 | 3830（100.0%） | 3254（100.0%） | 4274（100.0%） | 2677（100.0%） |

### 2.4 摘要与图文承载量

| 论文 | 摘要词数 | 编号正文词数 | 图 | 表 | 算法框 | 行间公式块 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| PIMCOMP | 143 | 3830 | 10 | 2 | 1 | 2 |
| CIMFlow | 150 | 3254 | 7 | 1 | 1 | 0 |
| UpDLRM | 141 | 4274 | 11 | 2 | 1 | 3 |
| 本稿前五章 | 142 | 2677 | 7 | 2 | 0 | 9 |

摘要的共同任务是确定对象、说明问题和概括方案。PIMCOMP 与本稿在摘要报告量化结果，CIMFlow 与 UpDLRM 采用定性效果表述。图表、公式和算法框分别承担接口、执行关系或完整结果矩阵，正文规模与实际占页分别检查。

## 3. PIMCOMP：章节组织分析

全文把架构与执行模型置于编译之前。操作流的冲突、依赖和启动间隔进入后续适应度；两种模式贯穿估计、调度与实验。主要篇幅留给分块定义、联合优化及不同流水粒度的实现。

### 3.3 章间交接与可借鉴处

第三章把硬件变成操作和并行条件，第四章随后使用这些条件建立估计器。HT 适应度段的详细示例承担从任务数到核心完成时间的推导；LL 两段接着处理层间依赖。示例的长度随推导任务分配。

搜索编码还引入每核节点数量上限。阅读时将这类求解限制与物理容量分别记录，便于判断候选空间受到哪些条件约束。算法描述需要同时交代可变对象和合法动作。

实验以总体趋势开启，再用负载及模式差异解释边界。能量段先建立共同计算工作，再讨论活跃核心与时长；存储与编译时间各自检验可执行性和实用性。方法与评价之间存在可追踪的对象交接。

## 4. CIMFlow：全文章节与逐段职责

全文把硬件抽象、指令表达、编译和模拟集中到框架章。其内部顺序沿输入与中间表示推进，评价则分开考察软件策略和硬件配置，再研究两者的交互。

### 4.1 小节组织

含下级列展示层级规模，直接正文列用于区分父级引导与细节。表内直接正文互斥，章词数由逐段表加总。

| 原小节／引导 | 含下级词数 | 直接正文词数 | 含下级段落／条目 |
| --- | ---: | ---: | --- |
| [II-A Digital CIM Preliminaries](https://arxiv.org/html/2505.01107v1#S2.SS1) | 189 | 189 | 2P |
| [II-B Related Works and Our Motivation](https://arxiv.org/html/2505.01107v1#S2.SS2) | 350 | 350 | 3P |
| [III-A Framework Overview](https://arxiv.org/html/2505.01107v1#S3.SS1) | 244 | 244 | 2P |
| [III-B ISA Design](https://arxiv.org/html/2505.01107v1#S3.SS2) | 382 | 382 | 5P |
| [III-C Compilation Flow](https://arxiv.org/html/2505.01107v1#S3.SS3) | 618 | 618 | 9P |
| [III-D Simulator Design](https://arxiv.org/html/2505.01107v1#S3.SS4) | 204 | 204 | 2P |
| [IV-A Experimental Setup](https://arxiv.org/html/2505.01107v1#S4.SS1) | 185 | 185 | 2P |
| [IV-B Compilation Optimization Evaluation](https://arxiv.org/html/2505.01107v1#S4.SS2) | 161 | 161 | 2P |
| [IV-C Architectural Configuration Exploration](https://arxiv.org/html/2505.01107v1#S4.SS3) | 254 | 254 | 3P |

### 4.2 完整逐段索引

| 原段 ID | 类型 | 词数 | 句数 | 段首定位 | 职责与承接 |
| --- | --- | ---: | ---: | --- | --- |
| [S1.p1](https://arxiv.org/html/2505.01107v1#S1.p1) | P | 79 | 3 | Recent advances in… | DNN 需求与数据搬移问题引出 CIM，建立研究领域。 |
| [S1.p2](https://arxiv.org/html/2505.01107v1#S1.p2) | P | 63 | 3 | Mainstream CIM designs… | 用模拟与数字计算机制区分技术对象，确定数字 CIM 范围。 |
| [S1.p3](https://arxiv.org/html/2505.01107v1#S1.p3) | P | 82 | 4 | However, fully realizing… | 从专用设计进入模型、映射与硬件的共同设计空间，提出工具需求。 |
| [S1.p4](https://arxiv.org/html/2505.01107v1#S1.p4) | P | 81 | 3 | While various software… | 按流程覆盖和硬件假设比较现有工具，为具体容量问题留出位置。 |
| [S1.p5](https://arxiv.org/html/2505.01107v1#S1.p5) | P | 89 | 4 | In particular, SRAM-based… | 把 SRAM 密度限制转成模型容纳、搬移和流水后果，收窄框架需求。 |
| [S1.p6](https://arxiv.org/html/2505.01107v1#S1.p6) | P | 62 | 3 | To address these… | 概述框架组成与探索用途，引入技术贡献。 |
| [S1.I1.i1.p1](https://arxiv.org/html/2505.01107v1#S1.I1.i1.p1) | C | 36 | 2 | We propose CIMFlow,… | 贡献：连接编译和模拟，形成可用的设计评价工作流。 |
| [S1.I1.i2.p1](https://arxiv.org/html/2505.01107v1#S1.I1.i2.p1) | C | 24 | 1 | We develop a… | 贡献：ISA 与分层抽象连接两侧的硬件配置。 |
| [S1.I1.i3.p1](https://arxiv.org/html/2505.01107v1#S1.I1.i3.p1) | C | 25 | 1 | We implement an… | 贡献：以分区和并行策略处理容量限制。 |
| [S2.SS1.p1](https://arxiv.org/html/2505.01107v1#S2.SS1.p1) | P | 72 | 3 | CIM architectures represent… | 解释位串行 MAC 及原位 MVM，为宏组织提供计算机制。 |
| [S2.SS1.p2](https://arxiv.org/html/2505.01107v1#S2.SS1.p2) | P | 117 | 4 | A digital CIM… | 定义宏单元组成，再从并行计算能力接到扩展需求。 |
| [S2.SS2.p1](https://arxiv.org/html/2505.01107v1#S2.SS2.p1) | P | 85 | 3 | The growing complexity… | 建立建模与编译两类工具的比较轴，准备具体文献分析。 |
| [S2.SS2.p2](https://arxiv.org/html/2505.01107v1#S2.SS2.p2) | P | 135 | 6 | However, most existing… | 逐项增加工具支持方式及架构假设，将引言概括落实到具体对象。 |
| [S2.SS2.p3](https://arxiv.org/html/2505.01107v1#S2.SS2.p3) | P | 130 | 6 | The above observations… | 把集成、灵活性与容量要求归入同一设计任务，接向第三章。 |
| [S3.SS1.p1](https://arxiv.org/html/2505.01107v1#S3.SS1.p1) | P | 79 | 3 | The design of… | 先给集成与可扩展原则，建立框架整体的解释层次。 |
| [S3.SS1.p2](https://arxiv.org/html/2505.01107v1#S3.SS1.p2) | P | 165 | 6 | As illustrated in… | 沿输入、ISA、两级编译和模拟输出说明工作流，使后续模块有共同接口。 |
| [S3.SS2.p1](https://arxiv.org/html/2505.01107v1#S3.SS2.p1) | P | 46 | 2 | As depicted in… | 把 ISA 定位为硬件层级和指令设计的连接点，安排本节范围。 |
| [S3.SS2.p2](https://arxiv.org/html/2505.01107v1#S3.SS2.p2) | P | 52 | 2 | Hardware Abstraction. At… | 定义芯片层连接、存储和执行单位，为跨核心调度提供对象。 |
| [S3.SS2.p3](https://arxiv.org/html/2505.01107v1#S3.SS2.p3) | P | 78 | 4 | The core-level abstraction… | 定义核心内部资源与地址空间，为存储管理和算子执行提供条件。 |
| [S3.SS2.p4](https://arxiv.org/html/2505.01107v1#S3.SS2.p4) | P | 70 | 4 | At unit level,… | 进入单元层宏组、广播与辅助运算，给复制和空间映射具体资源。 |
| [S3.SS2.p5](https://arxiv.org/html/2505.01107v1#S3.SS2.p5) | P | 136 | 6 | Instruction Design. To… | 给指令字段和扩展方式，将硬件资源落实为编译可生成的表达。 |
| [S3.SS3.p1](https://arxiv.org/html/2505.01107v1#S3.SS3.p1) | P | 78 | 3 | The CIMFlow compiler… | 把编译分成图级和算子级，交代各层处理的输入和目标。 |
| [S3.SS3.p2](https://arxiv.org/html/2505.01107v1#S3.SS3.p2) | P | 62 | 3 | CG-level Optimization. The… | 通过依赖分析和图压缩形成分区搜索的输入。 |
| [S3.SS3.p3](https://arxiv.org/html/2505.01107v1#S3.SS3.p3) | P | 98 | 4 | To address the… | 用容量约束引入分阶段执行及 DP，解释状态表示。 |
| [S3.SS3.p4](https://arxiv.org/html/2505.01107v1#S3.SS3.p4) | P | 82 | 4 | The compiler derives… | 对分区候选联合处理复制、映射和时间估计，给 DP 决策依据。 |
| [S3.SS3.p5](https://arxiv.org/html/2505.01107v1#S3.SS3.p5) | P | 54 | 3 | The final phase… | 将图级决策物化为跨核心数据流与 IR，交给算子级转换。 |
| [S3.SS3.p6](https://arxiv.org/html/2505.01107v1#S3.SS3.p6) | P | 43 | 2 | OP-level Optimization. Following… | 提出先虚拟再物理的算子映射层次，延续前面的 IR 输出。 |
| [S3.SS3.p7](https://arxiv.org/html/2505.01107v1#S3.SS3.p7) | P | 66 | 3 | The virtual mapping… | 按算子维度建立理想二维映射，为实际资源适配保留布局对象。 |
| [S3.SS3.p8](https://arxiv.org/html/2505.01107v1#S3.SS3.p8) | P | 89 | 4 | The physical mapping… | 通过 tiling、MVM 提取及访存标注适配实际资源，将理想表示转成可执行形式。 |
| [S3.SS3.p9](https://arxiv.org/html/2505.01107v1#S3.SS3.p9) | P | 46 | 2 | In the final… | 由优化 IR 生成 ISA 指令，闭合编译输出接口。 |
| [S3.SS4.p1](https://arxiv.org/html/2505.01107v1#S3.SS4.p1) | P | 87 | 3 | The CIMFlow simulator… | 说明模拟器实现、配置输入和资源粒度，承接生成的指令。 |
| [S3.SS4.p2](https://arxiv.org/html/2505.01107v1#S3.SS4.p2) | P | 117 | 5 | At core level,… | 从流水、冲突跟踪到指标输出说明评价怎样取得，接向实验。 |
| [S4.SS1.p1](https://arxiv.org/html/2505.01107v1#S4.SS1.p1) | P | 129 | 6 | To demonstrate how… | 交代配置与部件参数来源，定义编译和硬件探索两类实验。 |
| [S4.SS1.p2](https://arxiv.org/html/2505.01107v1#S4.SS1.p2) | P | 56 | 3 | We select representative… | 建立后文复用的负载分类并固定精度，给收益差异解释轴。 |
| [S4.SS2.p1](https://arxiv.org/html/2505.01107v1#S4.SS2.p1) | P | 69 | 2 | We evaluate our… | 定义软件基线并固定硬件，构成受控编译策略比较。 |
| [S4.SS2.p2](https://arxiv.org/html/2505.01107v1#S4.SS2.p2) | P | 92 | 3 | As illustrated in… | 从总体收益定位高收益模型，再解释分区中的复制机会。 |
| [S4.SS3.p1](https://arxiv.org/html/2505.01107v1#S4.SS3.p1) | P | 62 | 3 | The efficiency of… | 固定软件策略，开放计算资源与网络带宽变量。 |
| [S4.SS3.p2](https://arxiv.org/html/2505.01107v1#S4.SS3.p2) | P | 113 | 5 | For ResNet18, increasing… | 以两类负载的响应差异解释硬件扩展收益和能量取舍。 |
| [S4.SS3.p3](https://arxiv.org/html/2505.01107v1#S4.SS3.p3) | P | 79 | 3 | To provide insights… | 重新开放软件策略，观察硬件排序变化，检验联合探索的设计价值。 |
| [S5.p1](https://arxiv.org/html/2505.01107v1#S5.p1) | P | 126 | 6 | This paper presents… | 总结框架、容量优化及效果，并给出后续扩展方向。 |

### 4.3 框架内部的组织层次

总览先交代模型与配置怎样经过编译进入模拟。ISA 章节提供共享资源和指令表达，编译章节沿图级 IR 向算子级映射推进；模拟器直接消费生成结果。模块介绍通过中间对象连续连接。

虚拟映射与物理映射之间保留同一个布局对象，后一段增加实际资源限制。对本稿可借鉴的是表示、可行性和执行评价的层次，具体抽象仍围绕三维驻留与节点共享计算资源建立。

实验的控制条件参与推理：固定硬件比较软件，固定软件研究硬件响应，随后开放软件选择以观察配置排序变化。总体收益之后，正文挑出有解释价值的模型子集并讨论资源原因。

## 5. UpDLRM：全文章节与逐段职责

设计章沿输入假设的变化推进：均衡访问下选择几何分区，真实偏斜要求频率感知分配，缓存随后改变剩余访问工作。三级方案共同进入系统、组件和敏感性研究。

### 5.1 小节组织

含下级列展示层级规模，直接正文列用于区分父级引导与细节。表内直接正文互斥，章词数由逐段表加总。

| 原小节／引导 | 含下级词数 | 直接正文词数 | 含下级段落／条目 |
| --- | ---: | ---: | --- |
| [2.1. DLRM Model](https://arxiv.org/html/2406.13941v2#S2.SS1) | 305 | 305 | 3P |
| [2.2. UPMEM PIM Architecture](https://arxiv.org/html/2406.13941v2#S2.SS2) | 220 | 220 | 2P |
| [2.3. Motivation](https://arxiv.org/html/2406.13941v2#S2.SS3) | 151 | 151 | 1P |
| [3.1. Embedding Table Partitioning](https://arxiv.org/html/2406.13941v2#S3.SS1) | 504 | 504 | 4P |
| [3.2. Non-Uniform EMT Partitioning](https://arxiv.org/html/2406.13941v2#S3.SS2) | 337 | 337 | 2P |
| [3.3. Cache-Aware Non-Uniform Partitioning](https://arxiv.org/html/2406.13941v2#S3.SS3) | 570 | 570 | 4P |
| [4.1. Experimental Setup](https://arxiv.org/html/2406.13941v2#S4.SS1) | 220 | 220 | 2P |
| [4.2. Effectiveness of UpDLRM](https://arxiv.org/html/2406.13941v2#S4.SS2) | 355 | 355 | 2P |
| [4.3. Latency breakdown](https://arxiv.org/html/2406.13941v2#S4.SS3) | 205 | 205 | 3P |
| [4.4. Sensitivity Study](https://arxiv.org/html/2406.13941v2#S4.SS4) | 359 | 359 | 3P |

### 5.2 完整逐段索引

| 原段 ID | 类型 | 词数 | 句数 | 段首定位 | 职责与承接 |
| --- | --- | ---: | ---: | --- | --- |
| [S1.p1](https://arxiv.org/html/2406.13941v2#S1.p1) | P | 140 | 6 | Deep Learning Recommendation… | 从推荐服务规模定位 embedding 的容量和访存需求。 |
| [S1.p2](https://arxiv.org/html/2406.13941v2#S1.p2) | P | 141 | 6 | Due to the… | 沿 CPU–GPU 和 CPU-only 方案持续追问内存瓶颈，接到 DPU 机会。 |
| [S1.p3](https://arxiv.org/html/2406.13941v2#S1.p3) | P | 91 | 5 | UPMEM DPU is… | 以执行位置和存储体并行说明 DPU 加速的来源。 |
| [S1.p4](https://arxiv.org/html/2406.13941v2#S1.p4) | P | 149 | 10 | There exist several… | 把容量、通信、多线程和访问差异转成分区设计要求。 |
| [S1.p5](https://arxiv.org/html/2406.13941v2#S1.p5) | P | 202 | 9 | In this paper,… | 按三级设计概述系统与评估，方案顺序对应第三章结构。 |
| [S2.SS1.p1](https://arxiv.org/html/2406.13941v2#S2.SS1.p1) | P | 106 | 6 | Figure 1 shows… | 沿模型的数据流定位 embedding 层，提供应用对象。 |
| [S2.SS1.p2](https://arxiv.org/html/2406.13941v2#S2.SS1.p2) | P | 114 | 7 | Memory Capacity Requirement:… | 以表的组成和容量示例量化需求，让硬件分区约束有数量依据。 |
| [S2.SS1.p3](https://arxiv.org/html/2406.13941v2#S2.SS1.p3) | P | 85 | 4 | Memory Bandwidth Requirement:… | 从索引查询解释带宽需求，再加入访问差异引出负载问题。 |
| [S2.SS2.p1](https://arxiv.org/html/2406.13941v2#S2.SS2.p1) | P | 137 | 9 | The UPMEM PIM… | 按硬件层级给出存储和传输条件，明确 DPU 间数据路径。 |
| [S2.SS2.p2](https://arxiv.org/html/2406.13941v2#S2.SS2.p2) | P | 83 | 4 | Different from RRAM-based… | 补充核心计算、多线程与带宽能力，为方法模型提供资源参数。 |
| [S2.SS3.p1](https://arxiv.org/html/2406.13941v2#S2.SS3.p1) | P | 151 | 7 | Embedding layers are… | 将应用瓶颈与硬件容量接回表驻留和分区任务，交给设计章。 |
| [S3.SS1.p1](https://arxiv.org/html/2406.13941v2#S3.SS1.p1) | P | 57 | 3 | We partition each… | 在均衡访问假设下定义可容纳的矩形分区及变量。 |
| [S3.SS1.p2](https://arxiv.org/html/2406.13941v2#S3.SS1.p2) | P | 128 | 6 | As shown in… | 按前向执行阶段区分输入传输、查询与返回，为时间模型建立分解。 |
| [S3.SS1.p3](https://arxiv.org/html/2406.13941v2#S3.SS1.p3) | P | 99 | 7 | Each embedding lookup… | 用硬件访问粒度曲线筛选参数范围，提前提供可测量的设计依据。 |
| [S3.SS1.p4](https://arxiv.org/html/2406.13941v2#S3.SS1.p4) | P | 220 | 10 | Multiple DPUs perform… | 从三项时间估计建立优化目标和容量约束，说明可穷举的选择空间。 |
| [S3.SS2.p1](https://arxiv.org/html/2406.13941v2#S3.SS2.p1) | P | 99 | 6 | In the above… | 用真实访问分布检验均衡假设，建立下一层设计的必要性。 |
| [S3.SS2.p2](https://arxiv.org/html/2406.13941v2#S3.SS2.p2) | P | 238 | 13 | To accommodate this,… | 按频率进行容量约束的非均匀分配，并用同一案例检查均衡效果。 |
| [S3.SS3.p1](https://arxiv.org/html/2406.13941v2#S3.SS3.p1) | P | 129 | 6 | Existing studies leverage… | 引入共现缓存，同时指出其改变剩余访问分布，产生新的均衡任务。 |
| [S3.SS3.p2](https://arxiv.org/html/2406.13941v2#S3.SS3.p2) | P | 203 | 10 | To address this… | 把缓存和原表访问合并到同一分配准则，解释算法输入与资源划分。 |
| [S3.SS3.p3](https://arxiv.org/html/2406.13941v2#S3.SS3.p3) | P | 127 | 8 | Figure 7 illustrates… | 沿一次查询走完缓存命中、普通读取和结果合并，使算法动作具体化。 |
| [S3.SS3.p4](https://arxiv.org/html/2406.13941v2#S3.SS3.p4) | P | 111 | 6 | In the above… | 用容量敏感性解释缓存空间的代价，并说明采用的参数。 |
| [S4.SS1.p1](https://arxiv.org/html/2406.13941v2#S4.SS1.p1) | P | 84 | 5 | Workloads. We adopt… | 定义数据集、负载分组和采样规模，供后文对照使用。 |
| [S4.SS1.p2](https://arxiv.org/html/2406.13941v2#S4.SS1.p2) | P | 136 | 9 | Comparisons. We compare… | 定义比较系统的执行分工及本文硬件规模，为等待和流水解释提供前提。 |
| [S4.SS2.p1](https://arxiv.org/html/2406.13941v2#S4.SS2.p1) | P | 150 | 8 | Figure 8 illustrates… | 报告系统排序，再挑出聚合规模相关的差异和混合系统等待问题。 |
| [S4.SS2.p2](https://arxiv.org/html/2406.13941v2#S4.SS2.p2) | P | 205 | 11 | To learn the… | 用组件方法解释系统差异，再用弱收益案例及参数差异限定设计条件。 |
| [S4.SS3.p1](https://arxiv.org/html/2406.13941v2#S4.SS3.p1) | P | 70 | 4 | To study the… | 沿执行阶段定义时延分解，固定比较参数。 |
| [S4.SS3.p2](https://arxiv.org/html/2406.13941v2#S4.SS3.p2) | P | 73 | 3 | First, comparing different… | 把分量变化接到缓存与分区，讨论查询瓶颈的变化范围。 |
| [S4.SS3.p3](https://arxiv.org/html/2406.13941v2#S4.SS3.p3) | P | 62 | 3 | Second, comparing the… | 以双向通信比例接回方法模型；首句与数值方向相反，按数值及前文模型解释。 |
| [S4.SS4.p1](https://arxiv.org/html/2406.13941v2#S4.SS4.p1) | P | 100 | 7 | In Figure 8,… | 回访总体观察，用合成输入控制访问分布，分离敏感性变量。 |
| [S4.SS4.p2](https://arxiv.org/html/2406.13941v2#S4.SS4.p2) | P | 148 | 6 | First, under the… | 用不同读取粒度的响应形态调用多线程流水机制。 |
| [S4.SS4.p3](https://arxiv.org/html/2406.13941v2#S4.SS4.p3) | P | 111 | 5 | Second, given a… | 把读取粒度阈值接回此前实验采用的参数范围，完成设计依据。 |
| [S5.p1](https://arxiv.org/html/2406.13941v2#S5.p1) | P | 200 | 10 | PIMPR utilizes ReRAM… | 按硬件体系和缓存机制比较已有工作，再定位多存储体分配任务。 |
| [S6.p1](https://arxiv.org/html/2406.13941v2#S6.p1) | P | 125 | 5 | This paper proposes… | 回收系统设计、负载均衡和总体效果，给出扩展方向。 |

### 5.3 由假设变化推动三级方法

均匀分区先假定访问均衡，以硬件读取粒度和时间模型决定参数。下一节用真实分布检验该假设，使非均匀分配有明确入口。缓存节又把前一方法的输入工作分布改变，因而需要同时衡量缓存和原表访问。

方法章已经包含读取粒度测量与缓存容量扫描。它们分别服务参数范围和空间选择；第四章承担整体效果及机制评价。度量数据的章节位置由所回答的问题确定。

组件段明确接回系统结果，敏感性研究再追问负载趋势，最终用硬件阈值解释此前参数选择。相关工作单列在评价之后，第二章因此集中于应用和真实硬件条件。

## 6. 跨论文归纳：结构怎样承担论证

### 6.1 引言与背景的深度分工

引言先让读者掌握研究任务，背景增加做设计判断所需的机制和数量依据。已有工具的比较在前两篇进入背景；应用论文把系统性相关工作移至末部，同时在背景详细介绍真实硬件。

前两章再次出现同一术语时，后文增加资源组织、执行条件或可计算后果。对本稿，权重驻留、节点串行计算与激活传输需要逐层增加属性，具体搜索规则由框架和算法承载。

### 6.2 建模、表示与算法的交接

建模段的输出应进入后文使用。操作序列及并行条件可以成为时间估计的前提，分块或 IR 可以成为映射的输入。沿对象检查章间接口，比只比较标题名称更能判断结构是否完整。

方法展开还需说明假设怎样影响决策空间。硬件容量、额外的搜索限制和执行规则分别记录；解释较弱收益时，先核对这些条件是否已经限制可改变的对象。

### 6.3 实验段落的职责与详细数据

| 任务 | 原文中的用法 | 对正文数据的要求 |
| --- | --- | --- |
| 总体效果 | 用汇总范围或关键值确认优势幅度 | 基线与统计范围清楚，完整矩阵交图表。 |
| 解释差异 | 选择高收益和弱收益负载，联系资源或依赖 | 数值对应具体解释对象。 |
| 检验边界 | 固定一个变量，观察另一变量的响应形态 | 保留代表区间、阈值与条件。 |
| 支撑设计选择 | 将测量回接参数范围或部署约束 | 段尾指出测量对设计的具体用途。 |

三篇均在正文报告关键数值。UpDLRM 的组件段还采用编号观察，分别讨论优势、弱收益案例和参数差异。学习其比较职责后，本稿按专属规范组织连续论证。

图引导句常用于切换测量对象；其后需要增加观察、条件或解释。泛化的效果评价和宣布将报告观察的句子，信息增量通常较低。段落功能随研究问题变化，句式无需统一成同一种小结。

### 6.4 图注与图内、正文的分工

| 论文 | 已核对的实验图 | 图注词数 | 主要承担的信息 |
| --- | --- | --- | --- |
| PIMCOMP | 8／9／10 | 10／9／8 | 指标、模式、归一化或复用对象。 |
| CIMFlow | 5／6／7 | 13／15／14 | 比较策略、架构变量；特殊深浅色编码另用短句。 |
| UpDLRM | 8／9／10／11 | 10／12／19／16 | 指标和基线、分解对象、数据集与读取参数。 |

实验图注先说明测量对象与比较内容。图内图例、坐标和子图标题承载相应字段，正文选择数值解释趋势。特殊归一化或编码在图注保留，完整数学定义与分析量正文同处。图注长度结合栏宽与模板观察，参考样本提供信息分工依据。

### 6.5 逐句研读时的检查方式

对一个原段先确定其新增认识，再按句序标记前提、条件、观察、解释和边界。指代应接住已经建立的对象，下一段应使用前段提供的事实或未解释完的差异。

时间分解能够定位差距；具体执行动作或资源行为提供机制解释。占比变化与绝对时间分别核对。UpDLRM §4.3 的通信趋势句和随后数值方向相反，原文的回接表述仍需逐项检查。

## 7. 当前英文稿的全文对照

本节按当前五章源文件统计，摘要和三项贡献保持冻结。正文包括 Dense／MoE FFN 链范围；当前稿由五章构成，结尾边界为 Evaluation。章节表描述当前内容。

### 7.1 章节规模

| 章 | 章节名 | 正文词数 | 段落／条目 | 占前五章 |
| --- | --- | ---: | --- | ---: |
| 1 | Introduction | 408 | 5P＋3C | 15.2% |
| 2 | Background and Motivation | 423 | 7P | 15.8% |
| 3 | Hardware Abstraction and Cost Model | 672 | 13P | 25.1% |
| 4 | Inference Framework | 644 | 10P | 24.1% |
| 5 | Evaluation | 530 | 9P | 19.8% |
| 合计 | 当前五章 | 2677 | 44P＋3C | 100.0% |

摘要为 142 词，独立列出。引言贡献合计 82 词；当前前两章的统计沿用已核验口径。

### 7.2 小节与直接引导

| 章／小节 | 含下级词数 | 直接正文词数 | 含下级段落／条目 |
| --- | ---: | ---: | --- |
| 2 / 3D CIM and MoE | 116 | 116 | 2P |
| 2 / Related Work and Motivation | 307 | 307 | 5P |
| 3 / 章级引导 | 19 | 19 | 1P |
| 3 / Architecture Model | 104 | 104 | 2P |
| 3 / Weight-Cube Representation | 203 | 203 | 3P |
| 3 / Operator Execution Time | 257 | 257 | 6P |
| 3 / Network Transfer Time | 89 | 89 | 1P |
| 4 / Overview | 48 | 48 | 1P |
| 4 / Framework Design | 237 | 0 | 3P |
| 4 / Weight Deployment | 48 | 48 | 1P |
| 4 / Inference Execution | 114 | 114 | 1P |
| 4 / Performance Profiler | 75 | 75 | 1P |
| 4 / Algorithms | 359 | 0 | 6P |
| 4 / Weight Mapping | 258 | 258 | 4P |
| 4 / Dataflow Scheduling | 101 | 101 | 2P |
| 5 / Experimental Setup | 169 | 169 | 2P |
| 5 / Overall Performance | 27 | 27 | 1P |
| 5 / Prefill Work Distribution | 175 | 175 | 3P |
| 5 / Decode Execution Choices | 159 | 159 | 3P |

### 7.3 当前稿逐段职责

| 源文件／行 | 类型 | 词数 | 句数 | 段首定位 | 当前职责 |
| --- | --- | ---: | ---: | --- | --- |
| [introduction:P1](english/sections/introduction.tex#L4) | P | 78 | 3 | Mixture-of-experts (MoE) models… | 建立专家权重需求与片上存储机会，再定位节点计算及激活传输。 |
| [introduction:P2](english/sections/introduction.tex#L6) | P | 67 | 2 | Each node executes… | 说明节点互斥执行，将布局和额外副本作为部署动作引入。 |
| [introduction:P3](english/sections/introduction.tex#L8) | P | 65 | 3 | The same resident… | 建立共同部署下的 Decode／Prefill 取舍及共享容量条件。 |
| [introduction:P4](english/sections/introduction.tex#L10) | P | 63 | 3 | Existing CIM compilation… | 按硬件表示和执行评价范围比较已有支持，引出共同模型。 |
| [introduction:P5](english/sections/introduction.tex#L12) | P | 53 | 4 | We present a… | 概述 FFN 范围和框架能力，接入技术贡献。 |
| [introduction:C1](english/sections/introduction.tex#L14) | C | 27 | 1 | We establish a… | 冻结贡献：统一三维容量与算子时间模型。 |
| [introduction:C2](english/sections/introduction.tex#L15) | C | 25 | 1 | We propose a… | 冻结贡献：连接部署、路由执行与性能分析。 |
| [introduction:C3](english/sections/introduction.tex#L16) | C | 30 | 1 | We design weight… | 冻结贡献：权重映射及数据流调度算法。 |
| [background:P1](english/sections/background.tex#L6) | P | 71 | 4 | CIM stores matrix… | 解释阵列内计算和三维共享电路，提供节点串行机制。 |
| [background:P2](english/sections/background.tex#L8) | P | 45 | 4 | An MoE layer… | 解释专家选择、共享专家及两阶段输入行为，建立 MoE 基础。 |
| [background:P3](english/sections/background.tex#L12) | P | 60 | 3 | CIM compilers model… | 比较硬件表示与时间参数，支撑统一模型贡献。 |
| [background:P4](english/sections/background.tex#L16) | P | 60 | 4 | Table REF compares… | 比较部署和执行覆盖，支撑框架贡献。 |
| [background:P5](english/sections/background.tex#L18) | P | 47 | 2 | Co-activated experts on… | 定义复制和空间重排，建立离线映射的资源矛盾。 |
| [background:P6](english/sections/background.tex#L20) | P | 97 | 3 | A fixed deployment… | 用同一部署上的两个执行说明副本与规约根的耦合。 |
| [background:P7](english/sections/background.tex#L29) | P | 43 | 3 | During prefill, per-expert… | 由跨专家节点工作引出 Prefill 分派，接到共同硬件参数。 |
| [hardware:P1](english/sections/hardware.tex#L4) | P | 19 | 1 | The hardware model… | 章级引导：声明硬件模型向映射和模拟提供的三类量。 |
| [hardware:P2](english/sections/hardware.tex#L17) | P | 56 | 4 | A Unit-Cube stores… | 按物理层级定义容量、计算单位和互连。 |
| [hardware:P3](english/sections/hardware.tex#L19) | P | 48 | 4 | Configurations specify geometry,… | 区分算子内部并行与节点互斥，说明原型表及标定来源。 |
| [hardware:P4](english/sections/hardware.tex#L23) | P | 113 | 7 | Each expert contains… | 定义逻辑投影、Weight-Cube 字段与空间分块，形成部署对象。 |
| [hardware:P5](english/sections/hardware.tex#L30) | P | 30 | 3 | The in-plane dimensions… | 给出物理放置和不重叠条件，供容量可行性使用。 |
| [hardware:P6](english/sections/hardware.tex#L32) | P | 60 | 4 | The operator execution… | 明确执行时间边界与外部通信向量，连接表示与评价。 |
| [hardware:P7](english/sections/hardware.tex#L36) | P | 22 | 3 | A section has… | 定义分块时间模型使用的几何量和单位。 |
| [hardware:P8](english/sections/hardware.tex#L38) | P | 56 | 3 | Planar. The input… | 以输入发射、计算及读出尾部建立 Planar 时间公式，并说明系数。 |
| [hardware:P9](english/sections/hardware.tex#L50) | P | 72 | 5 | Vertical. The MATH… | 以分组、堆叠与数字组合建立 Vertical 时间公式及深度取舍。 |
| [hardware:P10](english/sections/hardware.tex#L61) | P | 37 | 3 | The compiler chooses… | 确定深度选择、折叠及专家时间的编译顺序。 |
| [hardware:P11](english/sections/hardware.tex#L71) | P | 39 | 3 | For Planar, MATH… | 实例化 Planar 的公开时序锚点与拟合约定，提供标定依据。 |
| [hardware:P12](english/sections/hardware.tex#L73) | P | 31 | 2 | For Vertical, 3D-FPIM's… | 实例化 Vertical 的原始时间组成与向量加法参数。 |
| [hardware:P13](english/sections/hardware.tex#L77) | P | 89 | 5 | The expert's external… | 由通信字节数定义链路时间和可用日历，给出共同数据流语义。 |
| [methodology:P1](english/sections/methodology.tex#L7) | P | 48 | 2 | Spatial compilation supplies… | 沿块表示、部署、执行和反馈说明框架流程。 |
| [methodology:P2](english/sections/methodology.tex#L12) | P | 48 | 4 | A replica is… | 定义副本与节点驻留集合，连接装箱和运行时选择。 |
| [methodology:P3](english/sections/methodology.tex#L15) | P | 114 | 5 | Binding MATH maps… | 区分候选评分与完整执行，给出并发 Token 的资源推进。 |
| [methodology:P4](english/sections/methodology.tex#L27) | P | 75 | 3 | The profiler sums… | 定义 Decode 分量与 Prefill 下界，输出可解释的资源差距。 |
| [methodology:P5](english/sections/methodology.tex#L42) | P | 47 | 3 | Two single-replica initializers… | 定义两个起点及其使用的路由统计。 |
| [methodology:P6](english/sections/methodology.tex#L44) | P | 107 | 6 | A layer's root… | 以根位置传递建立跨层后缀评价，再说明增量搜索如何使用。 |
| [methodology:P7](english/sections/methodology.tex#L54) | P | 61 | 2 | Each track continues… | 按预算交替追加副本和同层位置交换，给出轨迹内门限。 |
| [methodology:P8](english/sections/methodology.tex#L56) | P | 43 | 3 | Validation compares the… | 用验证集比较同预算轨迹，明确多窗口选择口径。 |
| [methodology:P9](english/sections/methodology.tex#L59) | P | 30 | 2 | For decode, the… | 说明 Decode 联合搜索对象和剪枝依据。 |
| [methodology:P10](english/sections/methodology.tex#L61) | P | 71 | 4 | The prefill scheduler… | 沿节点累计工作更新解释 Prefill 分派，再给出汇聚与路由选择。 |
| [evaluation:P1](english/sections/evaluation.tex#L35) | P | 58 | 5 | We evaluate dense… | 定义模型、路由来源与采样划分。 |
| [evaluation:P2](english/sections/evaluation.tex#L37) | P | 111 | 7 | On a MATH… | 定义硬件、预算、评价器及指标基准。 |
| [evaluation:P3](english/sections/evaluation.tex#L41) | P | 27 | 1 | At 2 GB/s,… | 给出正式测试的总体收益范围。 |
| [evaluation:P4](english/sections/evaluation.tex#L45) | P | 89 | 6 | For fixed DeepSeek-V3… | 由固定工作建立平均下界，结合预算证据与链路边界解释饱和。 |
| [evaluation:P5](english/sections/evaluation.tex#L47) | P | 29 | 2 | The 20%-budget Planar… | 以绝对残差与窗口工作解释相对时间份额变化。 |
| [evaluation:P6](english/sections/evaluation.tex#L49) | P | 57 | 3 | With 20% deployments… | 在冻结部署上检验逐专家轮转与节点级分派的差异。 |
| [evaluation:P7](english/sections/evaluation.tex#L53) | P | 56 | 3 | Decode continues to… | 解释固定计算工作下的后段 Decode 收益与时延分量变化。 |
| [evaluation:P8](english/sections/evaluation.tex#L55) | P | 36 | 2 | In the Planar… | 用阶段冲突候选说明 Prefill 门限的选择作用。 |
| [evaluation:P9](english/sections/evaluation.tex#L57) | P | 67 | 4 | On frozen 20%… | 比较根选择和联合绑定，并说明跨层源位置传递。 |

### 7.4 对本稿的结构检查重点

硬件章输出的几何、执行时间和通信字节数，在框架章分别进入放置、候选评价和网络推进。后续修改沿这些对象检查定义与使用位置。公开时序锚点提供参数标定依据，独立精度验证需要相应数据和评价指标。

框架章区分表示与执行、性能分析及算法策略。两个阶段共享部署，Decode 与 Prefill 的取舍保持明确；每段预算和调度证据都应指向对应的资源变化。

实验保持图 4／5 总体及预算、图 6 预算机制、图 7 冻结部署调度的分工。按用户决定，跨带宽重放继续留在研究记录。后续写作按职责覆盖和知识递进判断，词数用于定位需要检查的内容。

## 8. 核验与复用记录

### 8.1 本轮覆盖

- CIMFlow 与 UpDLRM 保留完整逐段索引，共 73 个自然段或贡献条目；每条列出词数、句数、原文 ID 及职责。PIMCOMP 保留章间交接分析。
- 当前英文五章共 47 个自然段或贡献条目，采用实际源文件行号定位。行间公式前后的同段文字合并，公式块单独计数。
- 原文档前两章的 38 项词数与句数逐项重算一致。新增章节按相同词数规则处理，正文中的罗马数字操作序号剔除。
- 保留的逐段表各行互斥，按章加总与对照表的词数一致。小节总量可包含下级，直接正文另列。

### 8.2 原文对应与来源边界

保留的参考论文段落链接均使用固定 HTML 中实际存在的 ID。PDF 的浮动图表和跨栏文字通过原文对象核对，散文计量由 HTML 结构取得。

CIMFlow 框架图在 HTML 中提前挂于第二章，UpDLRM 复合外框含独立图号。正文词数排除这些图表，资源数量按真实图注编号统计；行间公式按最外层公式块计数。

### 8.3 本稿边界与文档使用

本轮更新研究文档及其阅读入口，英文与中文源稿、图形、实验数据和已编译 PDF 保持原样。原来用于记录逐轮改稿的历史篇幅由当前快照替代，当前冻结文本仍由英文源文件持有。

使用时从章级任务进入小节，再沿原段 ID 检查新增信息与前后交接。正文变动后复算本稿对照，参考论文版本固定；贡献、摘要及其他修改边界按用户最新决定执行。
