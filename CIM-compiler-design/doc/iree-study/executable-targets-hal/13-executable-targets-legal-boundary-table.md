# IREE 各后端的 executable-targets 产物

本文只记录 IREE backend 在 `executable-targets` 边界附近的 target IR 形态、
illegal/common dialect 处理方式，以及 backend 自己新增的 target surface。

| Backend | executable-targets 后的主形态 | illegal / converted away | legal / retained | backend-owned target surface |
| --- | --- | --- | --- | --- |
| LLVM CPU | LLVM-oriented executable body；默认继续 lower 到 LLVM dialect。 | `linalg` / `linalg_ext` 先转 loop；`scf` / `cf` / `arith` / `math` / `func` / `HAL` 在 LLVM conversion 中继续转掉或标 illegal。 | `LLVM` dialect 为主；conversion 中临时保留 `ModuleOp`、`iree_codegen.dispatch_config`、`iree_codegen.yield`。 | `iree_cpu` 基本是 attrs-only：pipeline、lowering config、MMA / data-tiled attrs；没有 CPU op dialect。 |
| LLVM GPU / CUDA | NVVM/LLVM-oriented executable body；目标是可序列化的 `llvm.module`。 | `linalg` / loops / `gpu` / `affine` / standard ops 在 final LLVMGPU lowering 中 converted away。 | `LLVM` + `NVVM` dialect；conversion 中临时保留 `gpu.module` / `gpu.yield` wrapper，以及 `iree_codegen.dispatch_config` / `yield`。 | `iree_gpu` 有丰富 attrs 和中间 ops。Attrs 包括 lowering config、pipeline、target、MMA/data-tiled/pipeline options；ops 包括 barrier、value barrier、subgroup scan、DMA、buffer resource cast 等。 |
| LLVM GPU / ROCm | ROCDL/LLVM-oriented executable body；和 CUDA 共享 LLVMGPU lowering 主体，最终走 ROCDL。 | 与 CUDA 同族：`linalg` / loops / `gpu` / `affine` / standard ops 在 final LLVMGPU lowering 中消失；ROCDL conversion 继续处理 GPU、vector、arith、func、memref 等。 | `LLVM` + ROCDL/AMDGPU 相关 dialect；临时保留 `iree_codegen.dispatch_config` / `yield`。 | 仍主要复用 `iree_gpu` attrs/ops；ROCm target 额外通过 target format、chip/features、tuning specs、ROCDL annotation 和 serializer/toolchain glue 表达目标差异。 |
| SPIR-V family / Vulkan | `spirv.module`；目标是 SPIR-V dialect module，再由 backend serializer 打包。 | final SPIR-V conversion 使用 full conversion，并把 unknown ops 动态判 illegal；因此非 SPIR-V target ops 不能残留。进入 SPIR-V 前会处理 affine、memref storage class、i64 emulation、unsupported float buffers、HAL interface/binding 等。 | `spirv` dialect module；少量 ABI/resource lowering 后进入 `spirv.module` 内部 passes。 | 主要复用 `iree_gpu` attrs/ops 作为 configuration/lowering surface；SPIR-V 自身是最终 target dialect。Vulkan target 额外传播 executable target attr，并在 linking 中 trim/materialize SPIR-V target env。 |
| SPIR-V family / Metal | 仍走 SPIR-V codegen，executable-targets 后保留 `spirv.module`，后续 serializer 经 SPIR-V binary / MSL 路径。 | 与 SPIR-V family 相同：最终 target body 不保留 generic MLIR graph。 | `spirv.module`。 | 没有单独 Metal codegen dialect；Metal target 的差异主要在 executable target format、serialization 和 SPIRV-Cross / metallib 相关 glue。 |
| SPIR-V family / WebGPU | 走 SPIR-V codegen，之后追加 WebGPU prepare，仍以 `spirv.module` 作为 target body。 | 与 SPIR-V family 相同；WebGPU prepare 还会扩展或移除 WGSL/WebGPU 不支持的 SPIR-V 形态。 | `spirv.module`，再加 WebGPU-compatible SPIR-V 约束。 | 没有单独 WebGPU codegen dialect；差异主要是 WebGPU prepare pass、entry point rename、flatbuffer serialization。 |
| VMVX | VMVX / VM-consumable executable body；比 CPU/GPU 更依赖自定义 target dialect。 | VMVX conversion 明确把 MLIR `tensor` dialect 设为 illegal；HAL dialect 也在 HAL-to-VMVX conversion 中 illegal；后续 VM conversion 再把 VMVX dialect 转成 VM。 | VMVX conversion 阶段保留 `vmvx`、`util`、`func`、`scf`、`arith`、`affine`、`memref`。 | `vmvx` 有 runtime-facing ops：buffer descriptor、raw interface binding buffer、binary、copy、fill2d、unary。 |

## 当前读法

当前可见 backend 大致分三类：

| 类别 | 代表 | 边界特征 |
| --- | --- | --- |
| LLVM-family final target | LLVM CPU、CUDA、ROCm | executable-targets 内继续推进到 LLVM/NVVM/ROCDL 方向，消灭大部分 MLIR 常用计算/控制方言。 |
| SPIR-V-family final target | Vulkan、MetalSPIRV、WebGPUSPIRV | 共享 SPIR-V codegen，最终进入 `spirv.module`；backend 差异主要在 target env、post prepare、linking 和 serialization。 |
| VM-family/custom runtime target | VMVX | 边界更接近 VMVX/VM 可消费 IR，因此保留较多 MLIR 控制/索引/buffer 方言，但明确排除 MLIR `tensor` dialect。 |

`Local` target 只注册 local HAL device，不是独立 executable codegen backend。`WGSL`
目录当前只注册 WGSL pass surface；可见 WebGPU target 仍通过 SPIR-V codegen 加 WebGPU prepare
完成 translation。
