# Runtime ABI SPEC

## 1. 共同入口

```text
hal.executable.binary(format = "cim-executable", data = CimExecutable)
HAL export ordinal + workgroup grid + bindings + active profile
```

## 2. Array state

Loaded CIM executable拥有一块persistent Array backing storage。唯一`__cim_array_init` deployment export
包含全部Array Load；IREE module initializer在module instance注册时以`1x1x1` dispatch执行它并等待完成。
Compute exports不含Array Load，只读取固定weight views。

同一module instance中init一次、compute可执行多次。销毁并重建module/session是新deployment，可以重新init。
Runtime不提供lazy mapping、cache、eviction、remap、first-use load或推理期间weight reprogramming。

## 3. Compute invocation

```text
select ExportDef by HAL ordinal
for each workgroup(x,y,z):
  create/reset workgroup SRAM
  evaluate parameterized views
  execute ordered program
  release workgroup SRAM
```

不同compute dispatch只通过HAL binding buffers传递tensor values，不通过hidden SRAM或Action state通信。
Array在compute期间只读；SRAM状态只属于当前workgroup invocation。

Loader沿每个export的program operands汇总实际SRAM view的最高结束字节，按IREE原生4 KiB
workgroup-local-memory page向上取整，并写入该export的dispatch attrs。计算包含静态offset、
extents、byte strides及element size；任一extent为零的view不增加需求。SRAM view若含workgroup
系数，则需求保守取profile完整容量。512 KiB header字段始终表示硬件容量上限，不是每个入口
的分配量。每次调用只检查并清零当前export所需的pages；无SRAM访问的deployment入口需要0页。

## 4. Contest projection

Numeric runtime消费payload、bindings、dispatch metadata和profile，写回HAL output bindings。
Final `.cim.isa`是独立的比赛可读投影，不是numeric runtime input。
