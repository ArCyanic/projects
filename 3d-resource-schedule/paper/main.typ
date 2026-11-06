#import "components.typ": *

#set document(title: "A Deployment and Execution Framework for MoE Inference on 3D CIM Systems", author: ())
#set page(paper: "a4", margin: (x: 17mm, top: 18mm, bottom: 19mm), columns: 2, numbering: "1", number-align: center)
#set columns(gutter: 5.5mm)
#set text(font: ("Libertinus Serif", "Noto Serif CJK SC"), lang: "zh", region: "CN", size: 11pt, fill: ink)
#set par(justify: true, leading: 0.72em, first-line-indent: 1em, spacing: 0.55em)
#set heading(numbering: "1.1")
#show heading.where(level: 1): it => block(above: 12pt, below: 6pt, sticky: true)[#text(font: "Noto Sans CJK SC", size: 12pt, weight: "bold", it)]
#show heading.where(level: 2): it => block(above: 8pt, below: 4pt, sticky: true)[#text(font: "Noto Sans CJK SC", size: 11pt, weight: "medium", it)]
#set math.equation(numbering: "(1)")
#show math.equation: set text(font: "New Computer Modern Math", size: 9.2pt)
#show math.equation.where(block: true): set block(above: 5pt, below: 5pt)
#set figure(gap: 3pt, supplement: [Figure])
#show figure: set text(lang: "en", region: "US")
#show figure.caption: it => {
  set text(size: 8.5pt)
  set par(leading: 0.45em, justify: true, first-line-indent: 0pt)
  it
}
#set cite(style: "ieee")

#place(top, scope: "parent", float: true, block(width: 100%)[
  #align(center)[
    #text(font: "Noto Sans CJK SC", size: 19pt, weight: "bold")[A Deployment and Execution Framework\ for MoE Inference on 3D CIM Systems]
    #v(5pt)
    #text(size: 9pt, fill: rgb("#667481"))[Chinese Draft for DAC, October 2026]
  ]
  #v(8pt)
])

#block[
  #set par(first-line-indent: 0pt)
#text(lang: "en", region: "US")[*Abstract* The high storage density of three-dimensional compute-in-memory (3D CIM) enables all experts of mixture-of-experts (MoE) models to reside on-chip, eliminating off-chip memory accesses for weight reads. Existing CIM compilation and simulation frameworks adopt different hardware representations and execution models, complicating MoE deployment and performance evaluation across 3D CIM architectures. Weight mapping and dataflow scheduling under dynamic routing must also balance decode latency against prefill throughput. We propose a deployment and execution framework for MoE inference that establishes a unified hardware abstraction and cost model for 3D CIM, connecting weight deployment, inference execution, and performance analysis. The framework optimizes expert replicas, spatial layouts, and execution locations through mapping and scheduling algorithms. Across three MoE models, adding approximately 20% more expert replicas reduces decode latency and prefill batch latency by 15.18%–18.46% and 3.86%–12.61%, respectively, compared with a single-copy deployment balanced by the full workload.]

  #text(lang: "en", region: "US")[*Index Terms*—3D compute-in-memory, dataflow scheduling, mixture-of-experts, performance modeling, weight mapping.]
]

#include "sections/introduction.typ"
#include "sections/background.typ"
#include "sections/hardware.typ"
#include "sections/methodology.typ"
#include "sections/evaluation.typ"

#v(3pt)
#block[
  #set text(size: 8pt)
  #set par(first-line-indent: 0pt, leading: 0.4em)
  *人工智能辅助说明。* OpenAI GPT-6 (Codex) 与 Google Gemini 用于论文的文字组织、数据复核、示意图及绘图代码生成。
]
#metadata("body-end") <body-end>
#heading(numbering: none)[References]
#block[
  #set text(size: 8.3pt, lang: "en", region: "US")
  #set par(leading: 0.45em, first-line-indent: 0pt)
  #bibliography("references.bib", style: "ieee", title: none)
]
