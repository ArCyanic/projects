"""Plot the zero-copy Mapping comparison and capacity mechanism."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from experiments.plots.scientific_style import (
    FRAME,
    INK,
    MUTED,
    PAPER,
    configure,
    save,
)
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

_OCCUPANCY_CMAP = LinearSegmentedColormap.from_list(
    "occupancy",
    ("#F7F8F9", "#F3E1B8", "#D6A53A", "#735A20"),
)
_WORK_CMAP = LinearSegmentedColormap.from_list(
    "work",
    ("#F6F8FA", "#D7ECE8", "#77BCAF", "#1E6674", "#173B57"),
)


def run_zero_copy_mapping_plot(input_path: Path, output_dir: Path) -> int:
    report = json.loads(input_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    configure()
    _plot_comparison(report, output_dir / "zero-copy-mapping-comparison")
    _plot_heatmaps(report, output_dir / "zero-copy-hypergraph-heatmaps")
    return 0


def _plot_comparison(report, output):
    methods = (
        "round-robin",
        "compute-balanced",
        "capacity-constrained-hypergraph",
    )
    labels = ("Round-robin", "Compute-balanced", "Hypergraph")
    colors = ("#24557A", "#4D7455", "#B05A32")
    bandwidths = tuple(report["bandwidths"])
    mean_baseline = np.asarray(
        [
            report["bandwidths"][bandwidth]["compute-balanced"]["decode_mean_ns"]
            for bandwidth in bandwidths
        ]
    )
    p95_baseline = np.asarray(
        [
            report["bandwidths"][bandwidth]["compute-balanced"]["decode_p95_ns"]
            for bandwidth in bandwidths
        ]
    )
    with plt.rc_context(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
        }
    ):
        figure, axis = plt.subplots(figsize=(7.8, 3.8))
        row_labels = []
        row_colors = []
        row = 0
        for bandwidth_index, bandwidth in enumerate(bandwidths):
            for method, label, color in zip(methods, labels, colors, strict=True):
                candidate = report["bandwidths"][bandwidth][method]
                mean = mean_baseline[bandwidth_index] / candidate["decode_mean_ns"]
                p95 = p95_baseline[bandwidth_index] / candidate["decode_p95_ns"]
                axis.hlines(
                    row,
                    min(mean, p95),
                    max(mean, p95),
                    color=color,
                    linewidth=1.5,
                    alpha=0.75,
                )
                axis.scatter(
                    mean,
                    row,
                    s=44,
                    marker="o",
                    facecolor=color,
                    edgecolor=color,
                    linewidth=0.8,
                    zorder=3,
                )
                axis.scatter(
                    p95,
                    row,
                    s=24,
                    marker="D",
                    facecolor="white",
                    edgecolor=color,
                    linewidth=1.1,
                    zorder=3,
                )
                row_labels.append(f"{float(bandwidth):g} GB/s: {label}")
                row_colors.append(color)
                row += 1
        axis.set_xlabel("Normalized Decode speed")
        axis.set_yticks(np.arange(row), row_labels)
        for tick, color in zip(axis.get_yticklabels(), row_colors, strict=True):
            tick.set_color(color)
        axis.invert_yaxis()
        axis.axvline(1, color="#777777", linewidth=0.7, linestyle="--", zorder=0)
        for separator in (2.5, 5.5):
            axis.axhline(separator, color="#D9D9D9", linewidth=0.7)
        axis.grid(axis="x", color="#D9D9D9", linewidth=0.6)
        axis.set_axisbelow(True)
        axis.legend(
            handles=(
                Line2D(
                    [],
                    [],
                    color="#777777",
                    marker="o",
                    linestyle="none",
                    label="Mean",
                ),
                Line2D(
                    [],
                    [],
                    color="#777777",
                    marker="D",
                    markerfacecolor="white",
                    linestyle="none",
                    label="P95",
                ),
            ),
            frameon=False,
            ncol=2,
            loc="lower right",
        )
        axis.margins(x=0.08, y=0.05)
        figure.tight_layout()
        save(figure, output)


def _plot_heatmaps(report, output):
    low = report["bandwidths"][str(report["capacity_ablation_bandwidth_GBps"])]
    methods = (
        "compute-balanced",
        "capacity-relaxed-hypergraph",
        "capacity-constrained-hypergraph",
    )
    titles = (
        "Compute-balanced",
        "Hypergraph: capacity relaxed",
        "Hypergraph: capacity constrained",
    )
    occupancy = np.asarray([low[item]["node_occupancy"] for item in methods])
    work = np.asarray([low[item]["node_compute_work_ns"] for item in methods]) / 1e9
    figure, axes = plt.subplots(2, 3, figsize=(9.5, 5.0))
    occupancy_image = None
    work_image = None
    for column, title in enumerate(titles):
        occupancy_image = axes[0, column].imshow(
            occupancy[column].reshape(4, 4),
            cmap=_OCCUPANCY_CMAP,
            vmin=occupancy.min(),
            vmax=occupancy.max(),
        )
        work_image = axes[1, column].imshow(
            work[column].reshape(4, 4),
            cmap=_WORK_CMAP,
            vmin=work.min(),
            vmax=work.max(),
        )
        axes[0, column].set_title(title, pad=7)
        _annotate(axes[0, column], occupancy[column].reshape(4, 4), ".0f")
        _annotate(axes[1, column], work[column].reshape(4, 4), ".2f")
        for axis in axes[:, column]:
            axis.set_xticks(range(4))
            axis.set_yticks(range(4))
            axis.tick_params(length=0, colors=MUTED)
            for spine in axis.spines.values():
                spine.set_color(FRAME)
                spine.set_linewidth(0.65)
        axes[1, column].set_xlabel("Mesh column")
        if column == 0:
            axes[0, column].set_ylabel("Resident count\nMesh row")
            axes[1, column].set_ylabel("MoE compute work\nMesh row")
    occupancy_axis = figure.add_axes((0.925, 0.56, 0.014, 0.30))
    occupancy_bar = figure.colorbar(occupancy_image, cax=occupancy_axis)
    occupancy_bar.set_label("MoE resident count")
    work_axis = figure.add_axes((0.925, 0.13, 0.014, 0.30))
    work_bar = figure.colorbar(work_image, cax=work_axis)
    work_bar.set_label("MoE training compute work (s)")
    for colorbar in (occupancy_bar, work_bar):
        colorbar.outline.set_edgecolor(FRAME)
        colorbar.outline.set_linewidth(0.6)
        colorbar.ax.tick_params(colors=MUTED, length=3, width=0.6)
    figure.subplots_adjust(
        left=0.08,
        right=0.90,
        bottom=0.10,
        top=0.91,
        hspace=0.24,
        wspace=0.16,
    )
    save(figure, output)


def _annotate(axis, values, spec):
    threshold = (values.min() + values.max()) / 2
    for row in range(4):
        for column in range(4):
            axis.text(
                column,
                row,
                format(values[row, column], spec),
                ha="center",
                va="center",
                fontsize=8,
                color=PAPER if values[row, column] > threshold else INK,
            )
