#import "../components.typ": ink, rule

#figure(
  {
    set text(size: 8.1pt, lang: "en", region: "US", fill: ink)
    set par(first-line-indent: 0pt, leading: 0.35em, justify: false)
    set align(left)
    table(
      columns: (1.55fr, 1fr, 1fr, 1fr, 1.12fr, 0.9fr),
      inset: (x: 2pt, y: 3.5pt),
      stroke: none,
      align: (x, y) => if x == 0 { left + horizon } else { center + horizon },
      table.hline(stroke: 0.65pt + ink),
      table.header(
        [*Work*], [*3D*\ *capacity*], [*MoE*\ *routing*],
        [*Weight*\ *copies*], [*Runtime*\ *choice*], [*Joint*\ *D/P*],
      ),
      table.hline(stroke: 0.35pt + rule),
      [PIMCOMP @pimcomp2023], [—], [—], [✓], [—], [—],
      [CIM-MLC @cimmlc2024], [—], [—], [✓], [—], [—],
      [CIMFlow @cimflow2025], [—], [—], [✓], [—], [—],
      table.hline(stroke: 0.35pt + rule),
      [3D AIMC @buchel2025], [✓], [Token], [—], [—], [—],
      [OPTIMEX @sharma2025], [✓], [Profile], [—], [—], [—],
      table.hline(stroke: 0.35pt + rule),
      [*This work*], [✓], [Token], [✓], [✓], [✓],
      table.hline(stroke: 0.65pt + ink),
    )
    v(3pt)
    text(size: 7.3pt)[
      Routing uses per-token execution (Token) or activation statistics (Profile).
      Runtime choice selects resident replicas. Joint D/P optimizes decode latency
      and prefill throughput on one deployment.
      ✓: explicit scope; —: outside scope.
    ]
  },
  kind: table,
  supplement: [Table],
  caption: figure.caption(position: top)[Comparison of CIM and MoE frameworks.],
) <tab:framework-comparison>
