#import "@preview/algorithmic:1.0.7" as algorithmic

#let paper-algorithm(title, input, output, body) = {
  figure(
    block(
      width: 100%,
      breakable: false,
    )[
      #set text(size: 8.5pt)
      #set par(leading: 0.58em)
      #grid(
        columns: (1fr,),
        row-gutter: 1.4pt,
        align(left)[*Input:* #input],
        align(left)[*Output:* #output],
      )
      #v(2.8pt)
      #align(left, algorithmic.algorithm(body))
    ],
    kind: "algorithm",
    supplement: [Algorithm],
    caption: title,
  )
}

#let alg-key(body) = text(weight: "semibold", body)
