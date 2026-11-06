#let design-report-cn(
  title: "",
  subtitle: none,
  authors: (),
  date: none,
  body,
) = {
  set document(title: title, author: authors)
  set page(
    paper: "a4",
    margin: (left: 25mm, right: 25mm, top: 24mm, bottom: 25mm),
    numbering: "1",
    number-align: center,
    header: context {
      if counter(page).get().first() > 1 {
        set text(font: "Noto Sans CJK SC", size: 8.5pt, fill: luma(90))
        align(right, title)
        line(length: 100%, stroke: 0.4pt + luma(170))
      }
    },
    footer: context {
      if counter(page).get().first() > 1 {
        align(center, counter(page).display())
      }
    },
  )
  set text(
    font: ("Noto Serif CJK SC", "Libertinus Serif"),
    lang: "zh",
    region: "CN",
    size: 10.5pt,
  )
  set par(
    justify: true,
    leading: 0.72em,
    first-line-indent: (amount: 2em, all: true),
  )
  set figure(gap: 0.55em)
  set heading(numbering: "1.1.1")
  set math.equation(numbering: "(1)")
  show math.equation: set text(font: ("New Computer Modern Math", "Noto Serif CJK SC"))
  show math.equation: set block(spacing: 0.7em)
  show raw.where(block: true): set text(font: ("New Computer Modern Mono", "Noto Sans CJK SC"), size: 8.5pt)
  show figure.caption: it => {
    set text(size: 9pt)
    set par(justify: false, leading: 0.45em, first-line-indent: 0em)
    align(center, it)
  }

  show heading: it => {
    set text(font: "Noto Sans CJK SC")
    if it.level == 1 {
      block(above: 1.6em, below: 0.8em, it)
    } else if it.level == 2 {
      block(above: 1.15em, below: 0.45em, it)
    } else {
      it
    }
  }

  align(center)[
    #v(35mm)
    #text(font: "Noto Sans CJK SC", size: 22pt, weight: "bold", title)
    #if subtitle != none {
      v(12pt)
      text(font: "Noto Sans CJK SC", size: 14pt, subtitle)
    }
    #v(55mm)
    #if authors.len() > 0 {
      text(size: 12pt, authors.join("　"))
      v(10pt)
    }
    #if date != none { text(size: 11pt, date) }
  ]

  pagebreak()
  {
    set text(size: 9pt)
    set par(leading: 0.52em, first-line-indent: 0em)
    outline(title: [目录], depth: 2, indent: auto)
  }
  pagebreak()
  body
}

#let design-report-appendix(body) = {
  counter(heading).update(0)
  set heading(
    numbering: (..nums) => {
      let vals = nums.pos()
      let letter = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".at(vals.at(0) - 1)
      if vals.len() == 1 {
        "附录 " + letter
      } else {
        letter + "." + vals.slice(1).map(str).join(".")
      }
    },
  )
  pagebreak()
  body
}
