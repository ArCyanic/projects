"""Plot the QKVO mapping-object ablation."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def run_qkvo_obstruction_plot(input_path: Path, output: Path) -> int:
    report = json.loads(input_path.read_text(encoding="utf-8"))
    control, qkvo = report["trials"]
    comparison = report["comparison"]
    _configure_style()
    figure, axes = plt.subplots(
        1,
        2,
        figsize=(10.8, 4.3),
        gridspec_kw={"width_ratios": (1, 2.1)},
    )

    decode_speed = control["decode_mean_ns"] / np.asarray(
        (control["decode_mean_ns"], qkvo["decode_mean_ns"])
    )
    bars = axes[0].bar(
        (0, 1),
        decode_speed,
        width=0.62,
        color=("#0B78B5", "#E66500"),
        edgecolor="#26384F",
        linewidth=1.35,
    )
    bars[1].set_hatch("//")
    for bar, value in zip(bars, decode_speed, strict=True):
        axes[0].text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.035,
            f"{value:.2f}×",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
            color="#26384F",
        )
    axes[0].set_xticks((0, 1), ("Dense + MoE", "+ QKVO"))
    axes[0].set_ylabel("Normalized Decode speed")
    axes[0].set_ylim(0, 1.15)
    axes[0].set_title("(a) Decode speed", loc="left", pad=8)

    batches = np.asarray(control["prefill_batch_sizes"])
    ratios = 1 / np.asarray(comparison["prefill_makespan_ratio"])
    x = np.arange(len(batches))
    axes[1].fill_between(x, 1, ratios, color="#E66500", alpha=0.10)
    axes[1].plot(x, ratios, color="#E66500", linewidth=2.4)
    axes[1].scatter(
        x,
        ratios,
        s=52,
        color="#E66500",
        edgecolor="white",
        linewidth=1.0,
        zorder=3,
    )
    axes[1].axhline(
        1,
        color="#0085B8",
        linewidth=1.7,
        linestyle="--",
    )
    for position, ratio in zip(x, ratios, strict=True):
        axes[1].text(
            position,
            ratio + 0.02,
            f"{ratio:.2f}×",
            ha="center",
            va="bottom",
            fontsize=9,
            fontweight="bold",
            color="#E66500",
        )
    axes[1].text(
        x[-1],
        0.70,
        "with QKVO",
        ha="right",
        va="bottom",
        fontsize=10,
        fontweight="bold",
        color="#E66500",
    )
    axes[1].set_xticks(x, [f"T{batch}" for batch in batches])
    axes[1].set_xlabel("Token batch size")
    axes[1].set_ylabel("Normalized Prefill throughput")
    axes[1].set_ylim(0.48, 1.08)
    axes[1].set_title("(b) Prefill throughput", loc="left", pad=8)

    for axis in axes:
        axis.grid(axis="y", color="#D7E1E8", linewidth=0.8, linestyle="--")
        axis.set_axisbelow(True)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.spines["left"].set_color("#26384F")
        axis.spines["bottom"].set_color("#26384F")
        axis.spines["left"].set_linewidth(1.0)
        axis.spines["bottom"].set_linewidth(1.0)

    figure.tight_layout(w_pad=3.0)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output.with_suffix(".png"), dpi=300, bbox_inches="tight")
    figure.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    svg = output.with_suffix(".svg")
    figure.savefig(svg, bbox_inches="tight")
    svg.write_text(
        "\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n"
    )
    plt.close(figure)
    return 0


def _configure_style():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "font.size": 9,
            "axes.titlesize": 11,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "text.color": "#26384F",
            "axes.labelcolor": "#26384F",
            "xtick.color": "#26384F",
            "ytick.color": "#26384F",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
