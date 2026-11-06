# 从计算变换读到存储复用

三篇沿同一条思路展开，建议依次阅读：

1. [融合与权重复制为什么分阶段](iree-fusion-and-weight-replication.md)：从一个 Gemm 下降成多条 MVM，再合并为一次阵列计算，理解每种优化改变什么。
2. [权重复制怎样实现](weight-replication-implementation.md)：先算一个小矩阵，再看连续视图、全局试排和 IR 改写怎样落实它。
3. [SRAM 怎样按活跃期复用](sram-lifetime-allocation.md)：用三个缓冲区推导地址，理解别名、最后使用和原生 memory planner 的配合。

第一篇建立整体关系，后两篇沿具体例子深入实现。每篇中的源码链接放在相应机制旁。
