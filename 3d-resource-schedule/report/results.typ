#let result = json("/report/data/current-results.json")
#let number(value, digits: 2) = str(calc.round(value, digits: digits))
#let pct(value, digits: 2) = number(value, digits: digits) + "%"
#let value-range(values, digits: 2, suffix: "%") = number(values.at(0), digits: digits) + suffix + "–" + number(values.at(1), digits: digits) + suffix
#let profile-name(profile) = if profile == "planar" { "Planar" } else { "Vertical" }

#let performance-ratio(reduction) = 1 / (1 - reduction / 100)
