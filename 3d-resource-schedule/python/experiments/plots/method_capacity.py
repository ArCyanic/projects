"""Plot selected-deployment speed and throughput across replica budgets."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from experiments.plots.scientific_style import (
    BLUE,
    CORAL,
    FRAME,
    GOLD,
    INK,
    TEAL,
    configure,
    finish_axis,
    save,
)
from experiments.sequential_anchor_envelope import summarize_envelope
from matplotlib.lines import Line2D


def run_method_capacity_plot(input_paths: tuple[Path, ...], output_prefix: Path) -> int:
    """Write the shared main figure and selected-deployment marginal gains."""
    from paper.figures.build_figures import plot_main_results

    main = {}
    for path in input_paths:
        report = json.loads(path.read_text(encoding="utf-8"))
        main[report["hardware_profile"]] = summarize_envelope(report, path)
    configure()
    output_prefix.parent.mkdir(parents=True, exist_ok=True)
    plot_main_results(
        main,
        output_prefix.with_name(f"{output_prefix.name}-mainline"),
    )
    _plot_selected_gains(main, output_prefix.with_name("searched-capacity-curve"))
    return 0


def _plot_selected_gains(main, output):
    figure, axes = plt.subplots(2, 3, figsize=(10.9, 5.6), sharex=True)
    targets = (
        ("Decode speed", None, BLUE, "o"),
        ("Prefill T32 throughput", "32", TEAL, "s"),
        ("Prefill T128 throughput", "128", GOLD, "D"),
        ("Prefill T512 throughput", "512", CORAL, "^"),
    )
    for row, profile in enumerate(("planar", "vertical")):
        for column, bandwidth in enumerate((0.5, 2.0, 8.0)):
            axis = axes[row, column]
            entry = main[profile][str(bandwidth)]
            baseline = entry["baseline"]
            points = entry["selected"]
            budgets = np.asarray([p["budget"] for p in points])
            for label, token_count, color, marker in targets:
                values = np.asarray(
                    [
                        p["decode"]["mean_ns"]
                        if token_count is None
                        else p["prefill"][token_count]["mean_ns"]
                        for p in points
                    ]
                )
                base = (
                    baseline["decode"]["mean_ns"]
                    if token_count is None
                    else baseline["prefill"][token_count]["mean_ns"]
                )
                gains = base / values
                material = np.r_[False, np.diff(gains) >= np.diff(budgets) / 100]
                axis.plot(budgets, gains, color=color, linewidth=1.15, label=label)
                axis.scatter(
                    budgets,
                    gains,
                    marker=marker,
                    s=20,
                    facecolors="white",
                    edgecolors=color,
                    linewidths=0.8,
                )
                axis.scatter(
                    budgets[material],
                    gains[material],
                    marker=marker,
                    s=20,
                    color=color,
                    linewidths=0.8,
                    zorder=3,
                )
            axis.plot(
                budgets,
                1 + budgets / 100,
                color=FRAME,
                linewidth=0.8,
                linestyle=(0, (4, 3)),
            )
            axis.set_xticks((0, 5, 10, 15, 20))
            axis.set_xlim(-0.4, 20.4)
            axis.set_ylim(bottom=0.99)
            if row == 0:
                axis.set_title(f"{bandwidth:g} GB/s")
            if column == 0:
                axis.set_ylabel(f"{profile.title()}\nNormalized speed / throughput")
            finish_axis(axis)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    handles += [
        Line2D([], [], color=FRAME, linestyle=(0, (4, 3))),
        Line2D([], [], color=INK, marker="o", linestyle="none"),
        Line2D(
            [], [], color=INK, marker="o", markerfacecolor="white", linestyle="none"
        ),
    ]
    labels += [
        "Performance = 1 + budget",
        "Marginal performance gain >= budget increment",
        "Marginal performance gain < budget increment",
    ]
    figure.legend(handles, labels, ncol=4, frameon=False, loc="upper center")
    figure.supxlabel("Additional replica budget (%)")
    figure.tight_layout(rect=(0, 0.02, 1, 0.90), h_pad=1.3, w_pad=1.0)
    save(figure, output)
