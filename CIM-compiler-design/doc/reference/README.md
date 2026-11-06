# 外部参考与方案阅读

本目录汇集外部编译器、调度器和 CIM 硬件资料。

## Compiler与resource planning

- [01-mainstream-compiler-patterns.md](01-mainstream-compiler-patterns.md)：主流compiler如何提交planning结果。
- [02-ml-inference-memory-planners.md](02-ml-inference-memory-planners.md)：inference memory planner与arena reuse。
- [iree-device-resource-planning.md](iree-device-resource-planning.md)：IREE其他device的resource-planning机制。

## MLSys scheduler案例

- [mlsys/06-graph-scheduler-analysis.md](mlsys/06-graph-scheduler-analysis.md)：bounded search、pruning与tile simulation。
- [mlsys/07-vnrc-analysis.md](mlsys/07-vnrc-analysis.md)：partition、coupling、retention与recompute。
- [mlsys/09-rust-blp-analysis.md](mlsys/09-rust-blp-analysis.md)：convex subgraph、tile search与BLP selection。

## CIM硬件与NVM lifecycle

- [nvm-cim-weight-lifecycle.md](nvm-cim-weight-lifecycle.md)：NVM预烧录、静态驻留和低频重编程。
- [ada200v4-cim-isa-reference.md](ada200v4-cim-isa-reference.md)：两段式weight load/MVM、SRAM供给与依赖表达。
