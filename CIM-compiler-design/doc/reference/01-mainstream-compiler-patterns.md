# Mainstream Compiler Patterns

## Question

How do mainstream compilers represent whole-graph or whole-function resource
planning results? Are they permanent IR, analysis objects, attrs, rewritten ops,
or runtime metadata?

## OpenXLA / XLA

Relevant sources:

- [OpenXLA: From HLO to Thunks](https://openxla.org/xla/hlo_to_thunks)
- [OpenXLA: HLO dumps](https://openxla.org/xla/hlo_dumps)
- [`HloSchedule`](https://github.com/openxla/xla/blob/main/xla/hlo/ir/hlo_schedule.h)
- [`BufferAssignment`](https://github.com/openxla/xla/blob/main/xla/service/buffer_assignment.h)
- [`HeapSimulator`](https://github.com/openxla/xla/blob/main/xla/service/heap_simulator/heap_simulator.h)
- [`MemorySpaceAssignment`](https://github.com/openxla/xla/blob/main/xla/service/memory_space_assignment/memory_space_assignment.h)

XLA is the closest mainstream precedent for the current CIM question. Its flow
is roughly:

```text
HLO module
  -> HLO schedule on HloModule
  -> liveness / heap simulation / memory-space assignment
  -> optional HLO rewrites for copies/rematerialization/memory spaces
  -> BufferAssignment side object/proto
  -> executable metadata + thunk sequence
```

Key observations:

- HLO scheduling is whole-graph order planning. It runs before physical buffers
  exist and may simulate memory usage to reduce peak memory.
- `BufferAssignment` is the authoritative physical memory layout object. It maps
  logical buffers to allocations/slices and permits disjoint lifetimes to reuse
  memory. It is not rewritten back as ordinary HLO ops.
- Heap simulation is an analysis/solver mechanism. Its result depends on the
  chosen schedule and feeds one-off human dumps, not a permanent resource IR or production debug contract.
- Memory-space assignment is the part most analogous to SRAM/DRAM planning. It
  may color HLO layout/memory spaces, insert/schedule copies, and emit preset
  assignments.

The result is deliberately split:

| Fact | XLA carrier |
| --- | --- |
| execution order | `HloSchedule` on `HloModule` |
| memory-space choice | HLO layout/coloring plus copy rewrites |
| exact offsets/reuse | `BufferAssignment` / preset assignments |
| runtime execution | thunks plus executable metadata |
| temporary human inspection | before/after/buffer-assignment dumps |

## MLIR One-Shot Bufferize

Relevant sources:

- [MLIR Bufferization](https://mlir.llvm.org/docs/Bufferization/)
- [MLIR Pass Management](https://mlir.llvm.org/docs/PassManagement/)
- [MLIR Pattern Rewriter](https://mlir.llvm.org/docs/PatternRewriter/)
- [MLIR Dialect Conversion](https://mlir.llvm.org/docs/DialectConversion/)

One-Shot Bufferize uses the classic MLIR shape:

```text
tensor IR
  -> whole-function analysis state
  -> in-place / copy decisions
  -> rewrite to memref/alloc/copy facts
```

The plan is transient analysis state. Once decisions are made, they are
materialized by rewriting IR. It is not a persistent `buffer_plan` dialect.

## IREE Flow / Stream / HAL

Relevant sources:

- [IREE developer tips](https://iree.dev/developers/general/developer-tips/)
- [IREE Flow dialect](https://iree.dev/reference/mlir-dialects/Flow/)
- [IREE Stream dialect](https://iree.dev/reference/mlir-dialects/Stream/)
- [IREE Stream passes](https://iree.dev/reference/mlir-passes/Stream/)
- [IREE HAL dialect](https://iree.dev/reference/mlir-dialects/HAL/)
- [IREE HAL passes](https://iree.dev/reference/mlir-passes/HAL/)
- [IREE Codegen dialect](https://iree.dev/reference/mlir-dialects/IREECodegen/)
- [IREE CUDA HAL driver design](https://iree.dev/developers/design-docs/cuda-hal-driver/)
- [IREE AMD AIE plugin](https://github.com/nod-ai/iree-amd-aie)
- [MLIR-AIE](https://github.com/Xilinx/mlir-aie)
- [IREE invocation model](https://iree.dev/developers/design-docs/invocation-execution-model/)

IREE is the strongest mainstream reference for "reuse the infrastructure, but
do not hide the plan." Its public compiler stack separates graph partitioning,
resource/timeline scheduling, runtime command abstraction, and per-target
codegen:

```text
Flow:    tensor/dataflow partitioning -> dispatch regions/executables
Stream:  async resource program -> affinities, lifetimes, timepoints,
         allocation scheduling, command ops, reuse
HAL:     low-level device/runtime ABI -> buffers, fences/semaphores,
         command buffers, executable variants
Codegen: per-dispatch target lowering -> lowering config, translation info,
         target binary/object
```

Flow is about forming executable regions. It models execution data flow and
partitions dense tensor computation into compatible dispatch regions that can
be outlined into executable modules. This is worth copying as a vocabulary for
"what computation becomes one target invocation." It is not, by itself, a
physical resource planner.

Stream is IREE's closest public layer to whole-program resource scheduling. It
turns tensor programs into explicitly scheduled asynchronous programs: target
affinity, resource forms/sizes, concurrency, lifetimes, timepoints, and async
work are made visible. Its pass pipeline includes usage refinement,
timepoint propagation, transient allocation reuse, allocation scheduling, and
conversion from implicit `stream.async.*` resource management to explicit
`stream.cmd.*` commands. After allocation scheduling, aliasing and local
liveness erasure make the result a committed execution schedule, not a neutral
analysis cache.

HAL is intentionally a thin runtime/device boundary. IREE HAL models buffers,
semaphores/fences, command buffers, queue execution, and executable variants.
The CUDA/HIP HAL design notes make the key architectural point: the compiler is
expected to plan object lifetime, workload schedule, and synchronization; the
driver stack should not recover those decisions with hidden intelligence at
runtime.

Codegen lowering config is another useful pattern. IREE records per-dispatch
compilation choices through `CompilationInfoAttr`, `LoweringConfigAttr`, and
`TranslationInfoAttr`: tile sizes, workgroup size, and pass-pipeline selection
are explicit target-lowering facts. The docs also warn that these attributes do
not fully verify pipeline completeness. For CIM, the lesson is to use explicit
attrs/metadata for selected lowering choices, but not to confuse such attrs
with a complete physical placement proof.

The AMD AIE ecosystem is a closer accelerator analogy than ordinary GPU
backends. The IREE AMD AIE plugin shows the plugin shape: attach a target
backend to IREE's executable/HAL structure instead of forking the whole
compiler. MLIR-AIE shows why that plugin still needs target-specific planning:
AIE devices are spatial arrays of tiles with local memories, programmable DMAs,
stream switches, core code, and explicit data movement/connectivity. Those are
not generic Stream facts; they are hardware placement and movement decisions
inside or below the target backend.

## LLVM Backend Allocation

LLVM's backend schedulers and register allocators run over Machine IR. The
allocator may use live intervals, interference graphs, spill heuristics, and
side tables internally, but the selected result is written back as physical
register assignments and spill/reload instructions.
