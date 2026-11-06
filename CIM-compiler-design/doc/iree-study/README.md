# IREE 与 CIM 后端学习

- [IREE 全流程：Host/Device 双轨与 12 阶段](iree_deep_dive_framework.md)：以残差 MLP 解释计算、任务、资源和目标代码的演化。
- [Stage 9–11：Codegen 与 HAL 的衔接](iree_stages_9_10_11_deep_dive.md)：深入分块配置、循环变换、设备代码与运行时绑定。
- [从 IREE 到 CIM：本项目的架构适配](iree-cim-backend-deep-dive.md)：在全流程基础上，理解阵列映射、链接后物理化、SRAM 规划和运行时契约。
- [残差 MLP 输入与阶段 IR](native-12-stages/)：前两篇文档所用案例的输入、阶段转储及设备产物。
- [VM pipeline 阶段表](iree-vm-pipeline-stages.md)：各阶段职责与 HAL 子管线。
- [目标配置管线](executable-configuration-native-pipelines.md)：configuration pass 的组织与作用域。
- [各后端的目标 IR](executable-targets-hal/13-executable-targets-legal-boundary-table.md)：executable-targets 之后的 IR 形态。
