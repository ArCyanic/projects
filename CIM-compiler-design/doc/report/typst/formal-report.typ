#import "@preview/typographix-polytechnique-reports:0.2.1" as formal

#let report-title = [面向单阵列存算一体芯片的端到端编译器设计报告]
#let short-title = [存算一体编译器设计报告]
#let navy = rgb("153A5B")
#let cyan = rgb("007A8A")
#let red = rgb("B52A3A")

#set document(
  title: report-title,
  author: "洪龙伟、王敬宇",
)
#set text(
  lang: "zh",
  font: ("Noto Serif CJK SC", "New Computer Modern"),
  size: 10.5pt,
)
#show math.equation: set text(font: "New Computer Modern Math")
#set math.equation(numbering: "(1)")
#show: formal.apply.with(first-line-indent-all: true)

// Replace the template's unconstrained SVG heading ornament with a restrained
// rule. The original image expands to the full text width under Typst 0.15.
#show heading.where(level: 2): it => block(
  width: 100%,
  above: 14pt,
  below: 9pt,
  breakable: false,
)[
  #grid(
    columns: (1fr,),
    row-gutter: 1.5pt,
    text(font: "Noto Sans CJK SC", size: 16pt, weight: "bold", fill: cyan)[
      #counter(heading).display("1.1") #h(0.55em) #it.body
    ],
    line(length: 100%, stroke: 0.65pt + cyan.lighten(35%)),
  )
]

#show heading.where(level: 3): it => block(
  above: 11pt,
  below: 0pt,
  breakable: false,
)[
  #text(font: "Noto Sans CJK SC", size: 12.5pt, weight: "bold", fill: navy)[
    #counter(heading).display("1.1.1") #h(0.5em) #it.body
  ]
  #v(5.5pt)
]

#set page(margin: 0mm, numbering: none, fill: white)
#place(top + left, rect(width: 100%, height: 12mm, fill: navy))
#place(top + right, rect(width: 52mm, height: 12mm, fill: cyan))
#place(bottom + left, rect(width: 100%, height: 7mm, fill: navy))
#place(bottom + right, rect(width: 66mm, height: 7mm, fill: red))
#align(center + horizon)[
  #block(width: 150mm)[
    #text(font: "Noto Sans CJK SC", size: 14pt, weight: "medium", fill: cyan)[2026 知存科技杯]
    #v(16mm)
    #text(font: "Noto Sans CJK SC", size: 27pt, weight: "bold", fill: navy)[#report-title]
    #v(8mm)
    #line(length: 44mm, stroke: 1.4pt + red)
    #v(8mm)
    #text(size: 13pt, fill: navy)[存算一体编译器架构设计报告]
    #v(28mm)
    #grid(
      columns: (35mm, 1fr),
      row-gutter: 5mm,
      align: (right, left),
      text(fill: gray.darken(25%))[报告类型], [设计与实验报告],
      text(fill: gray.darken(25%))[团队成员], [洪龙伟、王敬宇],
    )
  ]
]
#pagebreak()

#set page(
  paper: "a4",
  margin: (top: 24mm, bottom: 22mm, left: 23mm, right: 23mm),
  numbering: "i",
  number-align: center + bottom,
)
#counter(page).update(1)
#heading(level: 1, numbering: none, outlined: true)[摘要]
#include "abstract.typ"
#pagebreak()

#outline(title: [目录], depth: 3, indent: 1em)
#pagebreak()

#counter(heading).update(0)
#counter(page).update(1)
#set page(
  numbering: "1",
  header: context {
    set text(font: "Noto Sans CJK SC", size: 8.5pt, fill: navy)
    grid(
      columns: (1fr, auto),
      align(horizon, short-title),
      align(right + horizon, [2026 知存科技杯]),
    )
    v(2pt)
    line(length: 100%, stroke: 0.45pt + cyan)
  },
  footer: context {
    align(center, text(size: 8.5pt, fill: gray.darken(20%))[#counter(page).display()])
  },
)
#show raw.where(block: true): it => block(
  width: 100%,
  fill: rgb("F5F7F9"),
  stroke: 0.4pt + rgb("D8E0E6"),
  radius: 3pt,
  inset: 7pt,
  breakable: true,
  text(font: "JetBrains Mono", size: 7.4pt, it),
)
#show raw.where(block: false): it => box(
  fill: rgb("F2F4F6"),
  radius: 2pt,
  inset: (x: 2.5pt, y: 1pt),
  text(font: "JetBrains Mono", size: 0.88em, fill: navy, it),
)
#show table: set text(size: 8.4pt)
#set table(inset: 4.5pt, stroke: 0.45pt + rgb("CBD5DC"))
#set figure(numbering: "1")
#show figure.where(kind: image): set figure(supplement: "图")
#show figure.where(kind: table): set figure(supplement: "表")

#include "chapter1.typ"
#include "chapter2.typ"
#include "chapter3.typ"
#include "chapter4.typ"
#include "chapter5.typ"
#pagebreak()
#include "chapter6.typ"
