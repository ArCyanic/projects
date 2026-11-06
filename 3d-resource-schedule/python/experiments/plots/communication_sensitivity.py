"""Plot Decode and Prefill Mesh-bandwidth sensitivity."""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch

PROFILE_LABELS = {
    "planar": "Planar",
    "vertical": "Vertical",
}
PREFILL_COLORS = (
    "#56b4e9",
    "#0072b2",
    "#009e73",
    "#e69f00",
    "#d55e00",
    "#7b3294",
)
DECODE_COLORS = ("#334155", "#d55e00")
COMPONENT_COLORS = {
    "mesh_service_ns": "#0072b2",
    "expert_compute_ns": "#64748b",
    "node_serialization_ns": "#e69f00",
    "collective_contention_ns": "#009e73",
}
COMPONENT_LABELS = {
    "mesh_service_ns": "Mesh service",
    "expert_compute_ns": "Expert compute",
    "node_serialization_ns": "Node serialization",
    "collective_contention_ns": "Collective contention",
}


def _apply_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.0,
            "text.color": "#1f2937",
            "axes.labelcolor": "#1f2937",
            "axes.edgecolor": "#334155",
            "axes.titleweight": "bold",
            "axes.titlesize": 9.2,
            "axes.labelsize": 8.2,
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "xtick.labelsize": 7.2,
            "ytick.labelsize": 7.2,
            "legend.fontsize": 7.2,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.6,
            "lines.markersize": 5.0,
            "lines.markeredgecolor": "white",
            "lines.markeredgewidth": 0.65,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def _prefill(trial: dict, token_count: int) -> dict:
    return next(
        point
        for point in trial["profile"]["prefill"]
        if point["batch_size"] == token_count
    )


def _relative(values: list[float], bandwidths: np.ndarray) -> np.ndarray:
    series = np.asarray(values, dtype=np.float64)
    return series / series[bandwidths == 1.0][0]


def _plot_latency(axis, payload: dict, panel: str) -> None:
    trials = payload["trials"]
    bandwidths = np.asarray(
        [trial["bandwidth_GBps"] for trial in trials], dtype=np.float64
    )
    x = np.arange(len(bandwidths))
    decode_mean = [
        trial["profile"]["decode"]["objectives"]["latency_mean_ns"] for trial in trials
    ]
    decode_p95 = [
        trial["profile"]["decode"]["objectives"]["latency_p95_ns"] for trial in trials
    ]
    axis.plot(
        x,
        _relative(decode_mean, bandwidths),
        marker="o",
        color=DECODE_COLORS[0],
        label="Decode mean",
    )
    axis.plot(
        x,
        _relative(decode_p95, bandwidths),
        marker="s",
        linestyle="--",
        color=DECODE_COLORS[1],
        label="Decode P95",
    )
    for token_count, color in zip(payload["prefill_token_counts"], PREFILL_COLORS):
        values = [
            _prefill(trial, token_count)["objectives"]["makespan_mean_ns"]
            for trial in trials
        ]
        axis.plot(
            x,
            _relative(values, bandwidths),
            marker="o",
            color=color,
            alpha=0.9,
            label=f"Prefill T{token_count}",
        )
    axis.axhline(1.0, color="#94a3b8", linewidth=0.9, zorder=0)
    axis.axvline(3, color="#cbd5e1", linewidth=0.8, linestyle=":", zorder=0)
    axis.set_title(
        f"({panel}) {PROFILE_LABELS[payload['hardware_profile']]} latency",
        loc="left",
        pad=5,
    )
    axis.set_ylabel("Latency relative to 1 GB/s")
    axis.grid(axis="y", color="#e2e8f0", linewidth=0.7)


def _plot_bottlenecks(axis, payload: dict, panel: str) -> None:
    trials = payload["trials"]
    bandwidths = np.asarray(
        [trial["bandwidth_GBps"] for trial in trials], dtype=np.float64
    )
    x = np.arange(len(bandwidths))
    bottom = np.zeros(len(trials), dtype=np.float64)
    for key, color in COMPONENT_COLORS.items():
        values = 100 * np.asarray(
            [
                trial["profile"]["decode"]["bottleneck"][key]
                / trial["profile"]["decode"]["bottleneck"]["objective_time_ns"]
                for trial in trials
            ]
        )
        axis.bar(
            x,
            values,
            width=0.62,
            bottom=bottom,
            color=color,
            edgecolor="white",
            linewidth=0.5,
        )
        bottom += values

    token_counts = (16, 128, 512)
    markers = ("o", "s", "D")
    for token_count, marker in zip(token_counts, markers):
        peak_link = [
            100 * _prefill(trial, token_count)["bottleneck"]["communication_pressure"]
            for trial in trials
        ]
        axis.plot(
            x,
            peak_link,
            color="#7b3294",
            marker=marker,
            linestyle="--",
            label=f"Prefill T{token_count} peak link",
        )
    axis.set_title(
        f"({panel}) {PROFILE_LABELS[payload['hardware_profile']]} bottlenecks",
        loc="left",
        pad=5,
    )
    axis.set_ylabel("Critical-path share / utilization (%)")
    axis.set_ylim(0, 105)
    axis.grid(axis="y", color="#e2e8f0", linewidth=0.7, zorder=0)
    axis.set_axisbelow(True)


def _plot(payloads: list[dict], output: Path) -> None:
    figure, axes = plt.subplots(2, 2, figsize=(7.15, 5.6), sharex=True)
    _plot_latency(axes[0, 0], payloads[0], "a")
    _plot_latency(axes[0, 1], payloads[1], "b")
    _plot_bottlenecks(axes[1, 0], payloads[0], "c")
    _plot_bottlenecks(axes[1, 1], payloads[1], "d")
    for axis in axes[1]:
        axis.set_xlabel("Mesh bandwidth (GB/s)")
    for axis in axes.flat:
        bandwidths = payloads[0]["bandwidths_GBps"]
        axis.set_xticks(
            np.arange(len(bandwidths)), [f"{value:g}" for value in bandwidths]
        )

    latency_handles, latency_labels = axes[0, 0].get_legend_handles_labels()
    component_handles = [
        Patch(facecolor=color, label=COMPONENT_LABELS[key])
        for key, color in COMPONENT_COLORS.items()
    ]
    link_handles, link_labels = axes[1, 0].get_legend_handles_labels()
    figure.legend(
        latency_handles,
        latency_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.04),
        ncol=4,
        frameon=False,
        title="End-to-end latency",
    )
    figure.legend(
        [*component_handles, *link_handles],
        [*[handle.get_label() for handle in component_handles], *link_labels],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.055),
        ncol=4,
        frameon=False,
        title="Decode critical path  ·  Prefill link pressure",
    )
    figure.tight_layout(rect=(0, 0.08, 1, 0.91), h_pad=2.0, w_pad=1.6)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output.with_suffix(".png"), dpi=320, bbox_inches="tight")
    figure.savefig(output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(figure)


def run_communication_sensitivity_plot(
    input_path: Path,
    vertical_input: Path,
    output: Path,
) -> int:
    payloads = [
        json.loads(input_path.read_text(encoding="utf-8")),
        json.loads(vertical_input.read_text(encoding="utf-8")),
    ]
    _apply_style()
    _plot(payloads, output)
    return 0
