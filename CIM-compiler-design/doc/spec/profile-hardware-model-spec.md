# 硬件参数

Competition profile 使用单个 CIM Array：

| 参数 | 值 |
| --- | ---: |
| SRAM 容量 | 524288 B |
| SRAM allocation 对齐 | 64 B |
| Array 行数 | 1024 |
| Array 物理位列数 | 4096 |
| i8 权重单元列数 | 512 |

`cim.mvm` 与 `cim.bit` 支持 signed i8/i32 activation 和 i8 权重，结果为 i32。
激活位宽决定 8 或 32 轮 bit 计算；权重保持 i8。

这些参数用于 tiling、Array 放置和 SRAM 分配，并编码进 `CimExecutable` header。
