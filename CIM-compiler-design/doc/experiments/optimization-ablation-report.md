# CIM 优化消融实验报告

指标来源：同一次 native IREE/CIM 编译产生的 final `.cim.isa` 与 `.cim.payload`

运行期计数来自各入口的工作组程序，不乘以工作组网格。综合用例横向分支 `M=80` 时
`mTile=4`，每个工作组处理 4 行，网格为 20。

## 结论

四项优化可以组合，并已在一个 `integrated_showcase.onnx` 中同时触发。相对
`direct + sequential`，最终 `replicated + reuse` 的结果是：

| 指标 | baseline | 全优化 | 变化 |
| --- | ---: | ---: | ---: |
| MVM windows | 24 | 8 | -66.7% |
| activation bit rounds | 384 | 160 | -58.3% |
| SRAM peak | 12288 B | 10240 B | -16.7% |
| Array occupied cells（含结构零） | 81920 | 147456 | +80.0% |
| payload | 128197 B | 170520 B | +33.0% |

收益不是免费的：horizontal packing、heterogeneous fusion 和 weight replication
分别用更多同时存活的 SRAM、结构零或权重副本换取更少的 MVM windows/bit rounds。packing
把非连续目的缓冲 copy 回原 dest，综合用例 SRAM 峰值先升到 16384 B；lifetime reuse 再把它
降到 10240 B（相对 packing 后 −37.5%）。最终组合降低 recurring compute 与相对基线的 SRAM
峰值，只增加一次性部署容量。

当前保留上游横向融合的 `M<16` 限制，综合 Case 的两个 `M=1` producer 独立执行，
因此最终为 8 个窗口、160 个 bit rounds。四项优化及独立消融均在这一原生约束下验证。

## 实验条件

competition profile：

| 项目 | 值 |
| --- | ---: |
| physical CIM Array | 1 |
| Array shape | 1024 rows × 4096 bit columns |
| int8 cell view | 1024 × 512 |
| SRAM capacity | 512 KiB |
| SRAM alignment | 64 B |
| weight lifecycle | module 初始化时写 Array 一次；推理期间静止 |

本报告没有测 host wall-clock latency。当前 runtime 是功能性 numeric executor，host
时间不能代表目标 CIM 延迟。MVM windows、activation bit rounds、SRAM arena peak 和静态
部署容量都直接来自最终物理程序，适合解释排布优化的收益与成本。

## 方法

变换 pass 与 SRAM allocator 是两个独立轴：

```text
optimization_pipeline = direct | packed | heterogeneous | replicated
sram_allocation        = sequential | reuse
```

`packed` 包含 horizontal packing；`heterogeneous` 在其上增加 heterogeneous
block-diagonal fusion；`replicated` 再增加 weight replication。默认主线是
`replicated + reuse`。

四条消融边只改变一个变量：

| 优化 | baseline | treatment | 模型 |
| --- | --- | --- | --- |
| horizontal packing | `direct + reuse` | `packed + reuse` | `resource_showcase` |
| heterogeneous fusion | `packed + reuse` | `heterogeneous + reuse` | `heterogeneous_fusion_showcase` |
| weight replication | `heterogeneous + reuse` | `replicated + reuse` | `weight_replication_showcase` |
| SRAM lifetime reuse | `replicated + sequential` | `replicated + reuse` | `integrated_showcase` |

## 单变量消融

### Horizontal packing

四个共享 activation 的 `[256,64]` 权重沿输出列合并。该 Case 的激活为 `[80,256]`，
每个工作组处理 4 行，因此 direct 入口是 16 个窗口而不是 4 个；packing 比仍为 4:1。

| 指标 | direct | packed | 变化 |
| --- | ---: | ---: | ---: |
| MVM windows | 16 | 4 | -75.0% |
| bit rounds | 128 | 32 | -75.0% |
| SRAM peak | 8448 B | 10240 B | +1792 B |
| SRAM copy | 2048 B | 6144 B | +4096 B |
| regions | 4 | 1 | -3 |
| Array occupied cells（含结构零） | 65536 | 65536 | 0 |
| payload | 83521 B | 73857 B | -9664 B |

零初始化由 reaching-write 分析确认：允许跨过与目标无别名的操作，遇到任何可能读写目标的操作即停止。综合用例的横向分支由此删除 16 组部分结果分配、零拷贝和加回目标；最终全优化程序的 copy 为 9984 B，payload 为 170520 B。

该优化不复制权重，也不增加 Array cells；四个 region 合并成一个。非连续 dest 的 packed
列块 copy 回原缓冲，与位串行 scratch 在 dispatch 内同时存活，使 SRAM peak 增加。

### Heterogeneous block-diagonal fusion

三个不同 producer 分别生成 `[1,64]`、`[1,96]`、`[1,128]` 形状的 activation，对应乘以不同形状的静态 consumer weight（分别为 `[64,32]`、`[96,64]`、`[128,96]`）；全局优化将三个激活值拼接输入，并将三组权重组织为块对角矩阵。该 Case 的激活行数为 1。

| 指标 | packed | heterogeneous | 变化 |
| --- | ---: | ---: | ---: |
| MVM windows | 6 | 4 | -33.3% |
| bit rounds | 192 | 128 | -33.3% |
| SRAM peak | 1536 B | 2688 B | +1152 B |
| SRAM copy | 4608 B | 4608 B | 0 |
| regions | 6 | 4 | -2 |
| Array occupied cells（含结构零） | 57344 | 92160 | +34816 |
| structural fragmentation | 4096 cells | 46080 cells | +41984 |
| payload | 79453 B | 106926 B | +27473 B |

收益与代价剖析：

1. **零额外搬运开销**：输入张量直接写入相邻 SRAM 空间，`SRAM copy` 在优化前后完全一致（均为 4608 B），未新增运行期数据搬移量。
2. **SRAM 峰值增长机制**：SRAM peak 增加 1152 B（从 1536 B 升至 2688 B），原因在于融合后的单个 Dispatch 必须同时保活三个分支的 activation 及其组合输出（`[1,192]`）与位串行 scratch，而基线允许各分支分阶段串行执行并释放临时空间。
3. **阵列空间与结构零权衡**：阵列占用增加 34816 个单元（57344 $\to$ 92160），主要来自于块对角布局中非对角区域填补的 46080 个结构零。该开销以单次部署容量换取了运行时 33.3% 的 MVM 窗口与位计算轮次削减。

### Weight replication

相同 `[256,128]` weight 被连续 activation rows 使用；复制 pass 将连续输入行和输出行组成
一个 block-diagonal MVM，并直接写连续最终输出视图。

| 指标 | heterogeneous | replicated | 变化 |
| --- | ---: | ---: | ---: |
| MVM windows | 4 | 1 | -75.0% |
| bit rounds | 128 | 32 | -75.0% |
| SRAM peak | 6656 B | 8192 B | +1536 B |
| SRAM copy | 6144 B | 6144 B | 0 |
| Array occupied cells（含结构零） | 32768 | 524288 | +491520 |
| payload | 46496 B | 528128 B | +481632 B |

四份 `[256,128]` 权重的有效数据共 131072 个单元；Pass 将它们排成一个
`1024×512` 稠密块对角矩形，另外写入 393216 个结构零。因此有效权重增加 300%，物理
Array 占用增加 1500%。复制 candidate 在完整 module inventory 无法放入单 Array 时不会应用。

### SRAM lifetime reuse

保持 `replicated` 变换完全相同，只切换 arena allocator。

| 指标 | sequential | reuse | 变化 |
| --- | ---: | ---: | ---: |
| SRAM peak | 16384 B | 10240 B | -37.5% |
| MVM windows | 8 | 8 | 0 |
| bit rounds | 160 | 160 | 0 |
| SRAM copy | 9984 B | 9984 B | 0 |
| Array occupied cells（含结构零） | 147456 | 147456 | 0 |
| payload | 170520 B | 170520 B | 0 |

组合 Case 包含多个不重叠的 dispatch-local buffer lifetime，能独立展示 allocator 的效果。

位串行展开为每个 MVM 分配一块 `[1,N]` i32 scratch。这些 scratch 生命周期互不重叠，
`reuse` allocator 会把它们叠放到同一 offset，`sequential` 不会——这是本条边收益的主要来源。

## 组合实验

`integrated_showcase.onnx` 有三个输入、三个输出，并在同一个 module inventory、Array plan、
payload 和 VMFB 中包含：

- horizontal branch：`[80,256]` activation，四个 `[256,64]` weight；
- heterogeneous branch：三个不同形状的 internal activation 和三个不同 consumer weight；
- replication branch：`[4,64]` activation rows 共享一个 `[64,64]` weight。

累计阶段结果：

| stage | regions | Array occupied cells（含结构零） | payload B | MVM windows | bit rounds | SRAM peak B | SRAM copy B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| direct + sequential | 9 | 81920 | 128197 | 24 | 384 | 12288 | 5888 |
| packed + sequential | 6 | 81920 | 118533 | 12 | 288 | 16384 | 9984 |
| heterogeneous + sequential | 5 | 86016 | 118968 | 11 | 256 | 16384 | 9984 |
| replicated + sequential | 5 | 147456 | 170520 | 8 | 160 | 16384 | 9984 |
| replicated + reuse | 5 | 147456 | 170520 | 8 | 160 | 10240 | 9984 |

最后两行证明 SRAM allocator 不改变 compute 或 deployment；前三个 transformation 可以累计
减少 MVM work。packing 之后 SRAM 峰值上升，allocator 再独立回收。

## 二维权重合法化实验

`legalization_showcase.onnx` 在一个 module 和一个静态 Array plan 中放置两个不同随机权重：

| 逻辑权重 `[K,N]` | 切分轴 | 均分结果 | 物理 region |
| --- | --- | --- | --- |
| `[128,768]` | N / 输出列 | `384 + 384` | `128×384` 两块 |
| `[1536,64]` | K / 输入行 | `768 + 768` | `768×64` 两块 |

合法化只选择整除的均匀 tile，不引入 padding。horizontal packing 只合并到单个 Array
可容纳的宽度，因此不会把两个 384 列 tile 重新合成超宽 MVM。

| regions | Array occupied cells（含结构零） | occupancy | MVM windows | bit rounds | SRAM peak | payload |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 4 | 196608 | 37.50% | 4 | 32 | 4736 B | 202362 B |

四块 region 位于唯一的 `1024×512` Array 且互不重叠。N 分支用两个输出列 extent 写入连续
输出切片；K 分支用 activation offset `0` 和 `768` 选择输入切片，再用 `elt.add` 合并两个
partial。`cim.bit` 的矩形 extent 是逻辑 mask 的物理表达；该 Case 同时证明二维切分、矩形
选择、静态共存和 K partial accumulation。

## 正确性与权重生命周期

`tests/test_official_numeric.py` 对参考结果和 IREE local CIM VMFB 的每个输出做 bit-exact 比较。
官方模型和 showcase 都使用规范化 ONNX 的 ONNX Runtime 结果。组合 Case 的三个输出均通过；weight replication Case 也覆盖连续最终输出
直写。数值矩阵覆盖五个官方模型和六个 showcase，并由独立的前端语义、静态权重、
视图地址与 SRAM 覆盖回归补充；当前清单由 `python -m pytest --collect-only -q` 获取。

自 `cim-expand-bit-serial` 落地后，payload 里就是 `cim.bit` 序列，runtime 逐 bit 执行并
按 `2^i` 重建带符号乘积。因此上述 bit-exact 比较**同时是位串行展开与符号位重建的
正确性 gate**：`.cim.isa` 与 payload 是同一条 op 列表的两个投影，不存在只在文本里成立的
指令序列。

最终 full 配置的 ISA 只有一个 deployment section：

```text
.deployment @__cim_array_init
```

五条 `cim.array.load.i8` 全部位于该 deployment section；所有 `.runtime` section 都没有
`cim.array.load`。因此权重只在 module 初始化时写入一次，推理阶段没有 Array write。

## 复现

从仓库根目录执行：

```bash
cmake --build iree-build --target iree-compile iree-run-module

conda run -n npu python tools/cim-showcase \
  --output-dir output/cim-showcase

conda run -n npu python -m pytest -q
```

查看组合 Case 的同源物理程序：

```bash
sed -n '1,120p' \
  output/cim-showcase/integrated_showcase/full/integrated_showcase.cim.isa
```

指标定义：

- `regions`：deployment section 中 `cim.array.load.i8` 数量；
- `programmed_cells`：所有 load region 的 `rows × int8_columns` 之和，包含块对角结构零；
- `MVM windows`：`cim.bit.*` 中 bit index 为 0 的指令数量，即完整 MVM 次数；
- `bit rounds`：所有 `cim.bit.*` 指令数量；
- `SRAM peak`：final ISA 触达的最高 SRAM byte address，含位串行 scratch；
- `SRAM copy`：`mem.copy.*` 写入的总字节数，含 bias 导入与 boundary import/export；
- `payload`：同次编译生成的 `.cim.payload` 文件大小。

这些是结构计数，不是目标芯片延迟。它们能直接回答每个 pass 减少了多少 MVM 工作，以及为此
付出了多少 Array、payload 和 SRAM 成本。
