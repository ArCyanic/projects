"""Plot linear scheduling-axis ablations."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from experiments.plots.scientific_style import (
    BANDWIDTH_STYLE,
    INK,
    configure,
    finish_axis,
    save,
)


def run_dataflow_linear_plot(inputs: tuple[Path, ...], output: Path) -> int:
    reports = tuple(json.loads(path.read_text(encoding="utf-8")) for path in inputs)
    grouped = {
        profile: sorted(
            (report for report in reports if report["hardware_profile"] == profile),
            key=lambda report: report["link_bandwidth_GBps"],
        )
        for profile in ("planar", "vertical")
    }
    configure()
    figure, axes = plt.subplots(2, 4, figsize=(11.6, 5.7), sharey="col")
    token_counts = (None, "32", "128", "512")
    titles = ("Decode", "Prefill T32", "Prefill T128", "Prefill T512")
    decode_labels = ("Nearest replica", "Dynamic root", "Joint planning")
    prefill_labels = ("Round-robin", "Cumulative work")
    for row, profile in enumerate(("planar", "vertical")):
        for report in grouped[profile]:
            bandwidth = f"{report['link_bandwidth_GBps']:.1f}"
            color, marker = BANDWIDTH_STYLE[bandwidth]
            label_offset = {"0.5": 9, "2.0": 1, "8.0": -9}[bandwidth]
            for column, token_count in enumerate(token_counts):
                values = _normalized_performance(report, token_count)
                axis = axes[row, column]
                x_values = np.arange(len(values))
                axis.plot(
                    x_values,
                    values,
                    color=color,
                    marker=marker,
                    markerfacecolor="white",
                    markeredgewidth=1.1,
                    linewidth=1.8,
                    markersize=4.8,
                    label=f"{report['link_bandwidth_GBps']:g} GB/s",
                    zorder=3,
                )
                for x, value in enumerate(values[1:], start=1):
                    axis.annotate(
                        f"{value:.2f}",
                        (x, value),
                        xytext=(0, label_offset),
                        textcoords="offset points",
                        ha="center",
                        va="bottom" if label_offset >= 0 else "top",
                        fontsize=7.3,
                        color=color,
                    )
        for column, title in enumerate(titles):
            axis = axes[row, column]
            if row == 0:
                axis.set_title(title, pad=8)
            axis.axhline(1, color=INK, linewidth=0.75, alpha=0.65)
            axis.set_xticks(
                np.arange(3 if column == 0 else 2),
                decode_labels if column == 0 else prefill_labels,
                rotation=24,
                ha="right",
            )
            finish_axis(axis)
        axes[row, 0].set_ylabel(f"{profile.title()}\nNormalized speed")
        for axis in axes[row, 1:]:
            axis.set_ylabel("Normalized throughput")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(
        handles,
        labels,
        frameon=False,
        ncol=3,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.005),
        handlelength=2.4,
        columnspacing=2.0,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.93), h_pad=1.2, w_pad=1.0)
    output.parent.mkdir(parents=True, exist_ok=True)
    save(figure, output)
    return 0


def _normalized_performance(report, token_count):
    if token_count is None:
        values = [stage["mean_ns"] for stage in report["decode"]["stages"]]
    else:
        values = [
            stage["metrics"][token_count]["mean_ns"]
            for stage in report["prefill"]["stages"][:2]
        ]
    baseline = values[0]
    return [baseline / value for value in values]
