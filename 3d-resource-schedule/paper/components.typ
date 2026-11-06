#let ink = rgb("#202B33")
#let navy = rgb("#254E70")
#let pale = rgb("#DDEAF3")
#let rule = rgb("#D7DEE4")

#let paper-figure(path, caption, wide: false, placement: top) = figure(
  image(path, width: 100%),
  caption: caption,
  placement: placement,
  scope: if wide { "parent" } else { "column" },
)

#let paper-table(caption, columns, ..cells) = figure(
  {
    set text(size: 8.1pt, lang: "en", region: "US")
    set par(leading: 0.42em, first-line-indent: 0pt)
    table(
      columns: columns,
      inset: (x: 3pt, y: 4pt),
      stroke: (x: none, y: 0.35pt + rule),
      align: (left, auto),
      ..cells,
    )
  },
  kind: table,
  supplement: [Table],
  caption: figure.caption(position: top, caption),
)

#let paper-algorithm(caption, body) = figure(
  block(width: 100%, inset: (top: 5pt, bottom: 5pt), stroke: (top: 0.65pt + navy, bottom: 0.65pt + navy))[
    #set text(size: 8.5pt, lang: "en", region: "US")
    #set align(left)
    #set par(leading: 0.48em, first-line-indent: 0pt)
    #body
  ],
  kind: "algorithm",
  supplement: [Algorithm],
  caption: figure.caption(position: top, caption),
)
