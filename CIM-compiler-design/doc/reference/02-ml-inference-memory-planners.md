# ML Inference Memory Planners

This note compares how inference systems represent and apply memory plans.

## Summary

| System | Plan representation | CIM relevance |
| --- | --- | --- |
| XLA buffer assignment / memory space assignment | Backend buffer assignment becomes executable metadata; some placement also appears in backend configs and schedules. | High for liveness, aliasing, in-place reuse, and executable memory metadata. Less direct for explicit scratchpad banks unless using memory-space-style placement. |
| TensorRT | Builder selects tactics and memory needs; serialized engine plan plus execution-context contract drives runtime. | High for selected-plan serialization, tactic/workspace coupling, and fail-at-build semantics. Opaque internals make it a pattern to avoid for research explainability. |
| Glow | Low-level address-only IR and AOT bundle materialize static addresses, memory classes, and copy decisions. | Very high. Closest architectural analogue for CIM static SRAM/bank planning. |
| TVM USMP | Extracted `BufferInfo` graph feeds a replaceable planner; selected pools/offsets are lowered back into TIR/codegen artifacts. | Very high. Best reference for planner interface shape, multiple pools, constants, and decoupling algorithms from IR passes. |
| TensorFlow Lite Micro | Runtime allocator uses whole-graph tensor lifetimes; optional offline plan is stored in model metadata as tensor offsets. | Medium-high. Small but valuable build-time rejection embedded arena model; less expressive than CIM needs. |

The strongest references for CIM are Glow and TVM USMP, with XLA as the best
reference for mature global liveness/aliasing semantics. TensorRT is important
for build-time selected plans and tactic/workspace coupling, but its opaque plan
format should not be copied. TFLM is useful as a minimal embedded baseline.

## XLA Buffer Assignment / Memory Space Assignment

Relevant sources:

- [OpenXLA: From HLO to Thunks](https://openxla.org/xla/hlo_to_thunks)
- [OpenXLA: XLA GPU architecture overview](https://openxla.org/xla/gpu_architecture)
- [OpenXLA: Aliasing in XLA](https://openxla.org/xla/aliasing)

XLA is relevant because buffer planning is not a local allocator bolted onto
runtime execution. The compiler schedules the HLO module, simulates peak memory,
may rematerialize to shorten lifetimes, then assigns buffer slices immediately
before lowering. Its buffer assignment flow is roughly:

```text
scheduled HLO
  -> HloDataflowAnalysis: logical HloValues
  -> HloAliasAnalysis: HloValues grouped into HloBuffers
  -> BufferAssignment: non-overlapping HloBuffers packed into slices
  -> Executable metadata used by thunks/runtime
```

XLA commits selected buffer decisions into backend executable structures; the runtime does not rediscover liveness. For CIM this is not permission to serialize planner objects: the selected memory facts must be materialized into the owning MLIR/IREE carriers before TargetBackend projection. Any dump remains one-off human inspection only.

XLA also shows that in-place forwarding must be a compile-time relation, not an
allocator accident. Compile-time input/output aliasing can request donation and
in-place update. If the runtime invocation does not donate an aliased input, XLA
protects correctness by allocating/copying instead of silently violating the
compiled contract. For CIM, that policy is too permissive if SRAM feasibility is
part of correctness: a non-donated or non-resident buffer should reject the
compiled invocation rather than trigger an unplanned SRAM allocation.

Memory space assignment is worth referencing only insofar as it models placement
among memory spaces. The stronger CIM lesson is not XLA's GPU-specific memory
hierarchy, but the representation split: global dataflow/liveness analysis feeds a
materialized executable plan, and runtime pointer binding follows that plan.

## TensorRT

Relevant sources:

- [TensorRT capabilities](https://docs.nvidia.com/deeplearning/tensorrt/latest/architecture/capabilities.html)
- [TensorRT: how TensorRT works / memory](https://docs.nvidia.com/deeplearning/tensorrt/10.16.0/architecture/how-trt-works.html)
- [TensorRT weight streaming](https://docs.nvidia.com/deeplearning/tensorrt/latest/inference-library/weight-streaming.html)

TensorRT build-time optimization produces a serialized engine plan. The builder
performs graph optimizations, layer fusion, format selection, tactic selection,
timing, and memory planning. Tactics and memory are coupled: a faster kernel may
require more workspace, builder memory-pool limits can eliminate tactics, and
the resulting plan captures the selected implementation choices.

```text
network definition + builder config
  -> optimized/fused graph
  -> tactic selection / timing cache
  -> activation + scratch + persistent memory requirements
  -> serialized engine plan
  -> execution context
```

TensorRT commits selected tactics into a serialized engine and execution context. For CIM this is only an analogy for build-time commitment; final execution facts must still come from `.cim.isa` emitted from verified carriers, not from a serialized planner/provenance object. The engine owns weight layout after deserialization; each execution context has persistent
memory and enqueue memory. Enqueue memory combines activation memory and
scratch/workspace. TensorRT can share activation blocks across disjoint
lifetimes and, where possible, place transient scratch in unused activation
regions. APIs also allow the application to provide enqueue memory for a context,
which turns the plan into an explicit runtime memory contract.

TensorRT's timing cache is not the memory plan, but it is relevant to CIM because
it stabilizes tactic selection across builds. A CIM compiler will likely need a
similar cache for array mappings, tilings, DMA schedules, and SRAM budgets, but
the chosen result must still be serialized as an inspectable selected plan.

## Glow

Relevant sources:

- [Glow paper](https://arxiv.org/abs/1805.00907)
- [Glow repository](https://github.com/pytorch/glow)
- [Glow LLVM 2018 slides](https://llvm.org/devmtg/2018-10/slides/Rotem-Levenstein-Glow.pdf)
- [NXP Glow memory analysis](https://www.nxp.jp/docs/en/application-note/AN13001.pdf)

Glow is one of the closest analogues for CIM. It lowers a neural network graph
through a high-level domain IR into a lower-level instruction-based,
address-only IR. That lower IR exists specifically so the compiler can do
instruction scheduling, static memory allocation, and copy elimination before
machine-specific code generation.

Plan representation moves from analysis into materialized lowering artifacts. The
high-level graph is not the executable resource plan. The lower IR and AOT
bundle encode concrete addresses and memory regions. AOT bundles separate
constant memory, mutable memory, and activation memory; activations are the
statically planned scratch arena. Accelerator-oriented Glow material also
discusses multiple memory banks, SRAM/DRAM/scratchpad distinctions, explicit DMA,
operand bank/layout constraints, and static allocation per memory bank.

This is the most CIM-shaped lesson in the survey: resource planning becomes real
only after addresses, banks, copies, and schedules are made explicit enough for
code generation and bundle emission.

## TVM Unified Static Memory Planner

Relevant sources:

- [TVM USMP RFC](https://discuss.tvm.apache.org/t/rfc-unified-static-memory-planning/10099)
- [Apache TVM repository](https://github.com/apache/tvm)

TVM USMP is directly relevant because it was motivated by embedded compilation
where separate Relay graph planning and TIR local storage rewriting miss global
reuse opportunities. The RFC argues for one planner that sees inter-operator
and intra-operator buffers together, because optimizing local workspaces first
and only later sharing them with graph tensors is suboptimal.

Plan representation is deliberately split:

```text
TIR module + pool configuration
  -> analysis extracts BufferInfo
  -> planner selects pool_id/pool_offset
  -> TIR/codegen is rewritten to use pool buffers and offsets
  -> generated metadata declares workspace/parameter buffer contracts
```

The planner input shape is especially useful:

```text
BufferInfo {
  uid
  size_bytes
  alignment
  conflicts        // liveness/interference
  pool_candidates  // legal memory classes
  pool_id
  pool_offset
}
```

USMP's most important architectural choice is that the algorithm interface is
not tied to one concrete IR pass. Analysis extracts sizes, alignments, conflicts,
and candidate pools; the selected plan is then applied back to TIR/codegen.
Multiple pools include both workspaces and constants/parameters, so the runtime
contract can name SRAM, DTCM, flash, or other memories separately.

## TensorFlow Lite Micro

Relevant source:

- [TFLM memory management](https://github.com/tensorflow/tflite-micro/blob/main/tensorflow/lite/micro/docs/memory_management.md)

TFLM is a small embedded baseline. It uses a single tensor arena divided into
head, temporary, and tail sections. The head holds non-persistent tensor buffers
and is sized by `GreedyMemoryPlanner`, which looks at the whole model graph and
reuses buffers with non-overlapping lifetimes. The tail holds persistent
allocations, while the temporary section handles scoped scratch-like allocations.

TFLM also supports offline-planned tensor allocations. The offline plan is model
metadata named `OfflineMemoryAllocation`, encoded as tensor offsets from the
head of the arena. An offset of `-1` delegates that tensor back to the runtime
greedy planner. Offline offsets may overlap when the planner knows lifetimes do
not overlap; runtime planning then fits the remaining tensors around fixed
offsets.

Plan representation therefore has two modes:

- default mode: runtime allocator computes a plan from whole-graph model facts;
- offline mode: selected offsets are serialized in model metadata and treated as
  fixed constraints by the runtime allocator.

For CIM, the offline mode is the more relevant one. A CIM runtime should not
repair an infeasible SRAM plan by opportunistically allocating around it.
Instead, the compiled artifact should contain the selected SRAM plan, and runtime
should verify that named pools, sizes, and placements match the contract.
