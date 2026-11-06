// 5 分钟答辩幻灯片 (16:9 Presentation Slides)
// 编译命令: typst compile doc/report/typst/presentation.typ output/pdf/cim-compiler-presentation.pdf

#set page(
  paper: "presentation-16-9",
  margin: (x: 1.2cm, top: 1.0cm, bottom: 0.9cm),
  header: none,
  footer: none,
)

#set text(
  font: ("Noto Sans CJK SC", "PingFang SC", "Heiti SC", "Arial"),
  size: 12pt,
  lang: "zh",
)

// 页面样式辅助函数
#let slide-title(title, category: none) = {
  if category != none {
    block(spacing: 2pt)[
      #text(size: 10.5pt, weight: "bold", fill: rgb("009BB0"))[#category]
    ]
  }
  block(spacing: 4pt)[
    #text(size: 19pt, weight: "bold", fill: rgb("17324D"))[#title]
  ]
  v(0.15cm)
}

#let badge(content, fill-color: rgb("EBF8FF"), text-color: rgb("2B6CB0")) = {
  box(
    fill: fill-color,
    radius: 4pt,
    inset: (x: 8pt, y: 4pt),
    baseline: 0%,
    text(size: 10pt, weight: "bold", fill: text-color)[#content]
  )
}

// -------------------------------------------------------------
// 第 1 页: 封面
// -------------------------------------------------------------
#align(center + horizon)[
  #v(-0.2cm)
  #text(size: 32pt, weight: "bold", fill: rgb("17324D"))[面向单阵列存算一体芯片的\ 端到端编译器设计]
  #v(0.45cm)
  #text(size: 16pt, weight: "medium", fill: rgb("4A5568"))[从 ONNX 高层模型到单阵列物理 ISA 的延迟物理化编译体系]
  #v(1.2cm)
  #rect(fill: rgb("F7FAFC"), stroke: 1pt + rgb("CBD5E0"), radius: 8pt, inset: (x: 32pt, y: 15pt))[
    #text(size: 13.5pt, weight: "bold", fill: rgb("2D3748"))[参赛团队：]
    #h(0.4cm)
    #text(size: 13.5pt, fill: rgb("4A5568"))[洪龙伟（队长 · 西安交通大学）、王敬宇（桂林电子科技大学）]
  ]
]

#pagebreak()

// -------------------------------------------------------------
// 第 2 页: 工作全貌
// -------------------------------------------------------------
#slide-title("工作全貌", category: "OVERVIEW")

#grid(
  columns: (1fr, 1fr, 1fr, 1fr),
  gutter: 14pt,
  [
    #rect(fill: rgb("F8FAFC"), stroke: 1.2pt + rgb("CBD5E0"), radius: 8pt, inset: (x: 14pt, y: 16pt), width: 100%, height: 11.8cm)[
      #text(weight: "bold", size: 14.5pt, fill: rgb("2B6CB0"))[1. IREE 全流程接入]
      #v(0.15cm)
      #line(length: 100%, stroke: 1.2pt + rgb("E2E8F0"))
      #v(0.6cm)
      #text(size: 11.5pt, fill: rgb("334155"))[
        #list(
          spacing: 22pt,
          [接入 IREE 原生 12 阶段],
          [标准 VMFB 封装专有载荷],
          [宿主控制与设备执行解耦],
          [外部 HAL 运行时无缝驱动],
        )
      ]
    ]
  ],
  [
    #rect(fill: rgb("F8FAFC"), stroke: 1.2pt + rgb("CBD5E0"), radius: 8pt, inset: (x: 14pt, y: 16pt), width: 100%, height: 11.8cm)[
      #text(weight: "bold", size: 14.5pt, fill: rgb("2B6CB0"))[2. 方言与降级体系]
      #v(0.15cm)
      #line(length: 100%, stroke: 1.2pt + rgb("E2E8F0"))
      #v(0.6cm)
      #text(size: 11.5pt, fill: rgb("334155"))[
        #list(
          spacing: 22pt,
          [专用 `cim` 方言语义建模],
          [读写副作用与目标传递],
          [4 级 Progressive Lowering],
          [物理空间约束与显式映射],
        )
      ]
    ]
  ],
  [
    #rect(fill: rgb("F8FAFC"), stroke: 1.2pt + rgb("CBD5E0"), radius: 8pt, inset: (x: 14pt, y: 16pt), width: 100%, height: 11.8cm)[
      #text(weight: "bold", size: 14.5pt, fill: rgb("2B6CB0"))[3. 权重排布与分块]
      #v(0.15cm)
      #line(length: 100%, stroke: 1.2pt + rgb("E2E8F0"))
      #v(0.6cm)
      #text(size: 11.5pt, fill: rgb("334155"))[
        #list(
          spacing: 22pt,
          [横向拼接 / 异构对角融合],
          [权重多行复制与试排保护],
          [两级 Tiling 结构化降级],
          [面积降序、逐行最左空位放置],
        )
      ]
    ]
  ],
  [
    #rect(fill: rgb("F8FAFC"), stroke: 1.2pt + rgb("CBD5E0"), radius: 8pt, inset: (x: 14pt, y: 16pt), width: 100%, height: 11.8cm)[
      #text(weight: "bold", size: 14.5pt, fill: rgb("2B6CB0"))[4. SRAM 资源管理]
      #v(0.15cm)
      #line(length: 100%, stroke: 1.2pt + rgb("E2E8F0"))
      #v(0.6cm)
      #text(size: 11.5pt, fill: rgb("334155"))[
        #list(
          spacing: 22pt,
          [补码位串行点积算术展开],
          [别名闭包与活跃区间推导],
          [64 字节对齐 Best-Fit 复用],
          [单根内存池与视图映射],
        )
      ]
    ]
  ]
)

#pagebreak()

// -------------------------------------------------------------
// 第 3 页: IREE - 全流程接入
// -------------------------------------------------------------
#slide-title("IREE - 全流程接入", category: "ARCHITECTURE")

#align(center + horizon)[
  #image("assets/iree-cim-architecture.pdf", width: 100%, height: 12.5cm, fit: "contain")
]

#pagebreak()

// -------------------------------------------------------------
// 第 4 页: 方言体系与 IR 渐进降级
// -------------------------------------------------------------
#slide-title("方言体系与 IR 渐进降级", category: "DIALECT & IR")

#align(center + horizon)[
  #image("assets/cim-ir-pass-isa-mapping.pdf", width: 100%, height: 12.5cm, fit: "contain")
]

#pagebreak()

// -------------------------------------------------------------
// 第 5 页: 权重排布 - 三大优化原语
// -------------------------------------------------------------
#slide-title("权重排布 - 三大优化原语", category: "WEIGHT OPTIMIZATION")

#align(center + horizon)[
  #image("assets/weight-optimization-primitives.pdf", width: 100%, height: 12.5cm, fit: "contain")
]

#pagebreak()

// -------------------------------------------------------------
// 第 6 页: 权重排布 - 综合优化效果
// -------------------------------------------------------------
#slide-title("权重排布 - 综合优化效果", category: "EVALUATION")

#align(center + horizon)[
  #image("assets/integrated-before-after.pdf", width: 100%, height: 12.5cm, fit: "contain")
]

#pagebreak()

// -------------------------------------------------------------
// 第 7 页: 权重排布 - 二维合法化切分
// -------------------------------------------------------------
#slide-title("权重排布 - 二维合法化切分", category: "2D LEGALIZATION")

#align(center + horizon)[
  #image("assets/legalization-before-after.pdf", width: 100%, height: 12.5cm, fit: "contain")
]

#pagebreak()

// -------------------------------------------------------------
// 第 8 页: SRAM 资源管理
// -------------------------------------------------------------
#slide-title("SRAM 资源管理 - 活跃期复用", category: "MEMORY MANAGEMENT")

#align(center + horizon)[
  #image("assets/sram-lifetime-before-after.pdf", width: 100%, height: 12.5cm, fit: "contain")
]

#pagebreak()

// -------------------------------------------------------------
// 第 9 页: 实验结果与深度归因
// -------------------------------------------------------------
#slide-title("实验结果与深度归因", category: "EXPERIMENTAL RESULTS")

#align(center + horizon)[
  #image("assets/optimization-evidence.pdf", width: 100%, height: 12.5cm, fit: "contain")
]

#pagebreak()

// -------------------------------------------------------------
// 第 10 页: 结论与交付
// -------------------------------------------------------------
#slide-title("结论与交付", category: "CONCLUSION")

#v(0.3cm)
#align(center)[
  #rect(fill: rgb("F7FAFC"), stroke: 1.5pt + rgb("009BB0"), radius: 8pt, inset: 22pt, width: 95%)[
    #text(size: 20pt, weight: "bold", fill: rgb("17324D"))[从 ONNX 到单阵列 CIM 物理程序的端到端编译交付]
    #v(0.5cm)
    #grid(
      columns: (1fr, 1fr),
      gutter: 24pt,
      align: left,
      [
        #text(weight: "bold", size: 13pt, fill: rgb("2B6CB0"))[1. 端到端链路完全可执行]
        #v(0.2cm)
        #text(size: 11pt, fill: rgb("4A5568"))[
          基于 IREE 插件机制构建专用后端，单次编译生成标准 VMFB 与专有存算指令，外部 HAL 同步驱动顺利运行。
        ]
      ],
      [
        #text(weight: "bold", size: 13pt, fill: rgb("2B6CB0"))[2. 软硬协同优化高度可组合]
        #v(0.2cm)
        #text(size: 11pt, fill: rgb("4A5568"))[
          延迟物理化范式支撑横向拼接、异构融合、权重复制与 SRAM 活跃期复用在同一模型中无冲突协同生效。
        ]
      ]
    )
  ]
  #v(1.0cm)
  #text(size: 18pt, weight: "bold", fill: rgb("17324D"))[感谢各位评委专家，请指正！]
]
