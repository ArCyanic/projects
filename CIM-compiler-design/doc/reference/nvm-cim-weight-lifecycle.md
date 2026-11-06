# NVM CIM inference weight lifecycle

## Conclusion

For inference-oriented non-volatile CIM, the normal execution model is **program the
trained weights before inference, keep them resident, and repeatedly apply changing
activations**. ReRAM and NAND Flash are physically reprogrammable, so this is not
read-only hardware; however, reprogramming normally belongs to deployment, model
replacement, calibration/refresh, or a deliberately designed training mode—not to
every inference or every MVM.

The strongest direct evidence is NeuRRAM. Its authors state that weight mapping gives
top priority to fitting all conductance matrices on one chip “such that no
re-programming is needed during inference.” The same chip has separate
weight-programming and MVM modes. Its weights are programmed with iterative
write–verify; the paper reports an average 8.52 set/reset pulses and estimates 56 us
per cell for an integrated implementation. This is an explicit program-then-infer
lifecycle, not a weight load in the online MVM loop [1].

## Lifecycle categories

| Lifecycle | Inference NVM-CIM status | Meaning |
|---|---|---|
| One deployment, static residence | Mainline | Offline-trained weights are programmed into NVM cells; inference repeatedly reads/computes with them. |
| Low-frequency reprogramming | Supported, outside the hot path | Model installation/replacement, device calibration, compensation for drift, or an occasional refresh. |
| Layer-by-layer dynamic weight swapping | Technically possible, but not the preferred NVM inference dataflow | It spends programming time and energy and consumes write endurance. NeuRRAM explicitly maps the whole model to avoid it [1]. If a model does not fit, the architecture needs more arrays/chips or must explicitly expose temporal reprogramming as a separate contract. |
| Training or online weight updates | A separate architecture/mode | Analogue NVM training has been demonstrated, but it requires update algorithms and write circuitry designed for repeated conductance changes; it is not implied by an inference-only CIM ISA [4]. |

“Weight stationary” here means stationary over inference execution. It does **not**
mean that the device can never be programmed again.

## NAND Flash and ReRAM are similar at the compiler boundary, not identical physically

### NAND Flash

The published 3-D NAND-CIM work is explicitly an **inference engine** and studies
input/weight mapping plus inference errors from NAND string-current drift and
variation [2]. A fabricated embedded-NAND CIM stores multi-level synaptic weights in
Flash cells, uses a program–verify scheme to establish their values, and subsequently
performs bit-serial 8-bit MAC operations [3]. These are deployment/programming and
inference/compute phases with different jobs.

Flash therefore gives an especially strong reason to keep weights stationary during
inference: establishing precise multi-level cell values is a program–verify operation,
whereas inference is a read/compute operation. A compiler may support model updates,
but should not silently model each layer invocation as another Flash programming
event.

### ReRAM/RRAM

ReRAM also stores weights as non-volatile conductances, but its cells can be selected
and updated more directly. That makes low-frequency remapping and specialized
in-memory training more plausible than with NAND Flash. It still does not make
reprogramming free. NeuRRAM uses incremental-pulse write–verify, separates
weight-programming mode from MVM mode, and deliberately places the full model so that
inference needs no reprogramming [1]. Its chip-in-the-loop fine-tuning procedure also
avoids reprogramming already mapped layers; remaining layers are fine-tuned in
software and then programmed progressively [1].

The practical distinction is therefore:

- both media naturally support static resident inference weights;
- ReRAM is more credible for architectures that intentionally expose updates or
  online training;
- NAND Flash makes frequent dynamic weight swapping still less attractive;
- neither fact authorizes a compiler to insert online programming unless the target
  ISA and hardware contract explicitly define it.

## What the competition contract says

The contest material describes a NAND-Flash route and says that the matrix parameters
are **stored in the CIM unit in advance**, after which the multiplier vector is
supplied. It asks the compiler to map, replicate, or split linear weights into CIM
cells. Its runtime ISA contains `cim.bit`, elementwise operations, and SRAM copies;
`cim.bit` receives a static `weight_pos`. There is no Array-program, weight-load,
erase, or write–verify instruction [5].

That evidence supports this competition interpretation:

```text
deployment: choose the physical weight layout and program the NVM image once
runtime:    issue cim.bit/MVM operations against immutable weight_pos regions
```

The competition contract has exactly one physical Array. All weights selected for a
deployment must therefore share that Array simultaneously. This still does not imply
runtime layer swapping: the ISA provides no operation with which to express such a
swap, and the project contract places programming in one initialization phase.
Capacity overflow is a deployment failure or a reason to choose a different static
layout/optimization; it must not be repaired by inserting ordered runtime weight
loads.

## Compiler consequences

An ordered `array.load -> mvm` pair is acceptable only if `array.load` is an IR-level
declaration of deployment placement. If it survives in the per-inference instruction
stream as a real NVM write, it contradicts both the contest ISA and the dominant NVM
inference lifecycle.

The clean ownership boundary is:

```text
deployment image
  static weight bytes/conductance targets
  physical array regions
  one-time programming metadata

runtime program
  SRAM activation/output movement
  cim.bit / MVM commands referencing weight_pos
  no weight-program operation
```

Therefore Array planning should spatially place and deduplicate static weights, while
payload emission should separate the deployment image from the runtime command
stream. Programming bytes, programming time, and occupied cells remain deployment
and capacity metrics; they are not recurring inference latency.

For block-diagonal fusion this changes the trade-off, but does not erase it:

- fewer MVM windows and bit rounds are recurring runtime gains;
- activation packing, if required, is a recurring runtime cost;
- diagonal-layout zeros and the larger bounding rectangle consume resident Array
  capacity;
- programming the fused layout is a one-time deployment cost;
- if all relevant weights remain resident, there is no per-inference weight reload
  penalty to charge against fusion.

## Primary sources

1. W. Wan et al., “A compute-in-memory chip based on resistive random-access
   memory,” *Nature* 608, 504–512 (2022).
   [DOI](https://doi.org/10.1038/s41586-022-04992-8) ·
   [open full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC9385482/).
   See “RRAM write–verify programming and conductance relaxation,” “Weight-mapping
   strategies,” and the description of the chip's three operating modes.
2. W. Shim and S. Yu, “System-Technology Codesign of 3-D NAND Flash-Based
   Compute-in-Memory Inference Engine,” *IEEE Journal on Exploratory Solid-State
   Computational Devices and Circuits* 7(2), 172–181 (2021).
   [DOI](https://doi.org/10.1109/JXCDC.2021.3093772).
3. M.-S. Kim et al., “An Embedded NAND Flash-Based Compute-In-Memory Array
   Demonstrated in a Standard Logic Process,” *IEEE Journal of Solid-State Circuits*
   57(2), 314–324 (2022).
   [DOI](https://doi.org/10.1109/JSSC.2021.3098671).
4. S. Ambrogio et al., “Equivalent-accuracy accelerated neural-network training
   using analogue memory,” *Nature* 558, 60–67 (2018).
   [DOI](https://doi.org/10.1038/s41586-018-0180-5). This is a primary example of an
   NVM system deliberately designed around analogue weight updates; it belongs to
   the training/update category rather than ordinary static inference.
5. 2026 知存科技杯赛题详情（仓库中的赛题原文转写）：
   [`doc/contest-detail.md`](../contest-detail.md), especially sections 2, 4.1 and
   4.2. The archived official document is
   `doc/archive/contest/2026知存科技杯-存算一体编译器架构设计.docx`.
