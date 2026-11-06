# 6　Runtime 执行：加载、部署与工作组上下文

VMFB 中的 `hal.executable.binary` 保存 `CimExecutable`。CIM external loader 接入 IREE
local-sync，CPU 上的功能执行器按 payload 顺序解释操作，用于数值验证；它不测量目标芯片时延。
实现见 [cim_executable.c](../../compiler_plugins/cim/runtime/cim_executable.c)，调用合同见
[Runtime ABI](../spec/runtime-abi-spec.md)。

## Loaded executable 保存什么

`iree_hal_cim_executable_t` 以内嵌的 `iree_hal_local_executable_t` 对接原生 export、dispatch attrs
和 payload 所有权。CIM 扩展字段只保存 export/view/program/string/data 表指针，以及持久 Array backing storage。
它不另存一份 SRAM 分配状态或 planner 结果。

加载时检查 magic、版本、section ranges、view/program 引用与 competition 硬件参数，并分配
`1024×512` 字节的 Array backing storage。载荷布局见 [payload 规范](../spec/cim-executable-payload-spec.md)。

## 一次性部署

```text
module instance 初始化
  → IREE util.initializer 创建 one-shot command buffer
  → dispatch __cim_array_init，grid=1×1×1
  → embedded constants 写入固定 Array views
  → queue execute / fence await
  → compute dispatch 读取常驻权重
```

Array 坐标已由编译器决定，runtime 不重新放置。初始化入口只运行部署操作，后续 compute 不含 Array load。
同一 loaded executable 共享持久 Array；销毁并重建 module/session 会建立新的部署。

## Workgroup SRAM

512 KiB 是硬件容量上限。Loader 沿每个 export 的实际 operands 计算 SRAM 最高访问字节，
向上取整为 IREE 原生 4 KiB local-memory pages，写入该 export 的 dispatch attrs。
无 SRAM 操作的部署入口需要 0 页；含 workgroup 地址系数时保守使用完整容量。

每次 workgroup 调用检查并清零它所需的 local-memory pages。不同 workgroup 不共享隐式 SRAM 状态；
跨 dispatch 的结果由 HAL binding buffers 传递。这个运行时重置不替代编译期覆盖证明：若只改写
边界的一部分，SRAM materializer 仍必须保留其他部分的原输入。

## 视图地址与操作分发

对当前 workgroup `(x,y,z)`：

```text
byteOffset = base + x*offsetX + y*offsetY + z*offsetZ
```

基地址来自 HAL binding、工作组 local memory、persistent Array 或 embedded data。
Shape 和 byte strides 由 payload 提供，地址常量项与系数由编译器检查可表示性。

| Payload kind | 执行函数与语义 |
| --- | --- |
| `CIMX_OP_ARRAY_LOAD` | 复用 `iree_hal_cim_transfer`，将 embedded 权重复制到 Array view |
| `CIMX_OP_TRANSFER` | `iree_hal_cim_transfer` 按 rank、extent、strides 搬运同类型元素 |
| `CIMX_OP_BIT` | `iree_hal_cim_bit` 计算一个 activation bit 的点积，覆盖 destination |
| `CIMX_OP_ELT` | `iree_hal_cim_elt` 执行 add/sub/mul/div，承担位权恢复、符号位相减与部分和累加 |

对 B 位 signed activation，编译器已经生成 B 轮 bit 操作与显式 Elt 重建：i8 为 8 轮，i32 为 32 轮。
Runtime 只执行这份顺序程序，不重新展开 MVM，也不读取 `.cim.isa` 文本。
