= Introduction

混合专家模型（MoE）通过为每个 Token 稀疏激活少量专家，将模型参数规模与单 Token 计算工作量解耦 @switch2022。然而，海量专家权重的存储与读取仍是推理系统的主要瓶颈：传统加速器需频繁从片外显存加载活跃专家权重，受制于片外显存带宽。三维存内计算（3D CIM）将高密度垂直堆叠存储与原位模拟乘加结合，支持全专家权重片上常驻，消除了权重读取的片外访存开销 @buchel2025 @jang2025 @lee2022。

全专家常驻片上后，性能瓶颈转移至节点内串行计算与跨节点网络通信。3D CIM 的阵列尺寸、堆叠深度与读出机制共同决定节点的专家驻留容量与算子执行时间；多层阵列共享外围电路使同节点内同时激活的专家须串行计算，而将活跃专家分散至二维网格（2D Mesh）的不同节点虽可实现多节点并发，输入分发与结果汇聚却需跨越片上网络传输。同一权重部署还需同时服务两类推理阶段：单 Token Decode 受限于关键路径时延，偏好通信局部性与就近的层输出汇聚位置以缩减网络跳数；多 Token 并发 Prefill 追求批处理吞吐，需将高频专家分散至不同节点以缓解热点串行积压。受限于片上三维容量预算，系统须协同规划离线专家副本配置、空间布局与在线执行位置。

现有编译框架与 3D MoE 部署方案尚未能贯通上述软硬件约束。存内计算编译与模拟框架（如 PIMCOMP @pimcomp2023、CIM-MLC @cimmlc2024、CIMFlow @cimflow2025）建立了从静态计算图到多核指令流的工具链，但均针对二维阵列与静态计算图设计，未涵盖动态 MoE 路由与运行时副本选择；近期 3D MoE 研究探索了堆叠阵列上的专家映射与操作图模拟（3D AIMC @buchel2025）及异构存储层间的专家投影放置（OPTIMEX @sharma2025），但各自采用特定硬件假设且聚焦单副本静态部署，未联合优化专家副本与两阶段运行时调度。

本文提出面向 3D CIM 的 MoE 部署与执行协同框架，以三维权重块（Weight-Cube）统一表征算子空间占用与本地执行时间，贯通离线空间装箱、多副本交替映射、在线路由分派与跨层时序评估。本文主要贡献如下：

+ #text(lang: "en", region: "US")[We establish a unified hardware abstraction and cost model for 3D CIM that captures 3D weight storage footprints and local execution times across computation and readout mechanisms.]

+ #text(lang: "en", region: "US")[We design weight mapping and dataflow scheduling algorithms that alternate replica allocation and spatial layout search offline, while planning replica binding and result aggregation online for decode and prefill.]

+ #text(lang: "en", region: "US")[We build a token-routed cross-layer execution simulator and bottleneck profiler; across three MoE models and two 3D CIM readout mechanisms, optimized deployments with approximately 20% additional expert replicas reduce decode latency by 15.18%–18.46% and prefill batch latency by 3.86%–12.61% over a workload-balanced single-copy baseline.]

硬件时间模型的完整推导、算法细节与扩展实验收录于补充材料。
