"""Plot canonical metrics aligned with the method-capacity mainline."""

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
    MUTED,
    PAPER,
    configure,
    finish_axis,
    save,
)
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

_DECODE_COMPONENTS = (
    ("expert_compute_ns", "专家计算", INK),
    ("node_serialization_ns", "节点串行", GOLD),
    ("mesh_service_ns", "Mesh 服务", BLUE),
    ("collective_contention_ns", "集合通信等待", CORAL),
)
_LOAD_CMAP = LinearSegmentedColormap.from_list(
    "node-load",
    ("#F5F7F9", "#D5E9E5", "#76BCAF", "#26727C", "#173B57"),
)


def run_method_capacity_diagnostics_plot(input_path: Path, output_dir: Path) -> int:
    """Write Decode, Prefill, and time-domain diagnostic figures."""
    report = json.loads(input_path.read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    configure()
    _plot_decode_components(
        report,
        output_dir / "method-capacity-decode-components",
    )
    _plot_prefill_mechanism(
        report,
        output_dir / "method-capacity-prefill-mechanism",
    )
    _plot_prefill_timeline(
        report["timeline"],
        output_dir / "prefill-node-load-timeline",
    )
    return 0


def _plot_decode_components(report, output):
    figure, axes = plt.subplots(2, 3, figsize=(11.2, 6.3), sharex=True)
    for row, profile in enumerate(("planar", "vertical")):
        for column, bandwidth in enumerate(("0.5", "2.0", "8.0")):
            axis = axes[row, column]
            curve = report["profiles"][profile][bandwidth]
            x = np.arange(len(curve))
            values = [
                np.asarray([point["decode_components_ns"][field] for point in curve])
                / 1e6
                for field, _, _ in _DECODE_COMPONENTS
            ]
            axis.stackplot(
                x,
                values,
                colors=[color for _, _, color in _DECODE_COMPONENTS],
                alpha=0.88,
                linewidth=0,
                zorder=2,
            )
            axis.plot(
                x,
                np.sum(values, axis=0),
                color=INK,
                linewidth=1.05,
                alpha=0.7,
                zorder=3,
            )
            finish_axis(axis)
            axis.set_title(f"{float(bandwidth):g} GB/s", pad=7)
            if column == 0:
                axis.set_ylabel(
                    f"{'Planar' if profile == 'planar' else 'Vertical'}\n"
                    "Decode 平均时延 (ms)"
                )
            if row == 1:
                _set_stage_ticks(axis)
    figure.legend(
        handles=tuple(
            Patch(facecolor=color, label=label)
            for _, label, color in _DECODE_COMPONENTS
        ),
        ncol=4,
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 1.005),
        columnspacing=1.7,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.94), h_pad=1.25, w_pad=1.0)
    save(figure, output)


def _plot_prefill_mechanism(report, output):
    cases = (
        ("planar", "2.0", "Planar · 2 GB/s · T512"),
        ("vertical", "8.0", "Vertical · 8 GB/s · T512"),
    )
    figure, axes = plt.subplots(2, 3, figsize=(11.2, 5.8), sharex="col")
    for row, (profile, bandwidth, label) in enumerate(cases):
        curve = report["profiles"][profile][bandwidth]
        spaces = [point["prefill"]["512"]["optimization_space"] for point in curve]
        x = np.arange(len(curve))
        _stacked_resource_pressure(
            axes[row, 0],
            x,
            spaces,
            "compute_service_exposure",
            "compute_balance_headroom",
            BLUE,
            GOLD,
        )
        _stacked_resource_pressure(
            axes[row, 1],
            x,
            spaces,
            "communication_service_exposure",
            "communication_balance_headroom",
            CORAL,
            "#E7B96A",
        )
        residual = [100 * space["execution_headroom"] for space in spaces]
        axes[row, 2].plot(
            x,
            residual,
            color=INK,
            marker="o",
            markerfacecolor=PAPER,
            linewidth=1.7,
            markersize=5,
        )
        axes[row, 2].set_ylim(bottom=0)
        for column in range(3):
            finish_axis(axes[row, column])
        axes[row, 0].set_ylabel(f"{label}\n占窗口完成时间 (%)")
    titles = (
        r"计算压力 $E_{comp}^{P}+H_{comp}^{P}$",
        r"通信压力 $E_{comm}^{P}+H_{comm}^{P}$",
        r"执行残差 $H_{exec}^{P}$",
    )
    for column, title in enumerate(titles):
        axes[0, column].set_title(title, pad=8)
        axes[1, column].set_xticks(
            (0, 5, 10, 15, 20),
            ("0%", "5%", "10%", "15%", "20%"),
            rotation=22,
            ha="right",
        )
    figure.legend(
        handles=(
            Patch(facecolor=BLUE, label="基础计算服务量"),
            Patch(facecolor=GOLD, label="计算峰均差"),
            Patch(facecolor=CORAL, label="基础通信服务量"),
            Patch(facecolor="#E7B96A", label="通信峰均差"),
        ),
        loc="upper center",
        bbox_to_anchor=(0.5, 1.01),
        ncol=4,
        frameon=False,
    )
    figure.tight_layout(rect=(0, 0, 1, 0.93), h_pad=1.1, w_pad=1.0)
    save(figure, output)


def _stacked_resource_pressure(
    axis,
    x,
    spaces,
    exposure_field,
    headroom_field,
    exposure_color,
    headroom_color,
):
    exposure = np.asarray([100 * space[exposure_field] for space in spaces])
    headroom = np.asarray([100 * space[headroom_field] for space in spaces])
    axis.stackplot(
        x,
        exposure,
        headroom,
        colors=(exposure_color, headroom_color),
        alpha=0.88,
        linewidth=0,
    )
    axis.plot(x, exposure + headroom, color=INK, linewidth=0.8, alpha=0.65)
    axis.set_ylim(bottom=0)


def _plot_prefill_timeline(timeline, output):
    figure, axes = plt.subplots(
        2,
        3,
        figsize=(11.2, 5.5),
        sharex="col",
        gridspec_kw={"height_ratios": (1.35, 1)},
    )
    image = None
    for column, token_count in enumerate(("32", "128", "512")):
        batch = timeline["batches"][token_count]
        time = np.asarray(batch["time_fraction"])
        node_utilization = np.asarray(batch["node_utilization"])
        aggregate = np.asarray(batch["aggregate_utilization"])
        image = axes[0, column].imshow(
            node_utilization,
            aspect="auto",
            origin="lower",
            extent=(0, 1, -0.5, node_utilization.shape[0] - 0.5),
            cmap=_LOAD_CMAP,
            vmin=0,
            vmax=1,
            interpolation="nearest",
        )
        axes[0, column].set_title(
            f"T{token_count}  ·  {batch['makespan_ns'] / 1e6:.1f} ms",
            pad=7,
        )
        axes[0, column].set_yticks((0, 5, 10, 15))
        axes[0, column].tick_params(length=0, colors=MUTED)
        for spine in axes[0, column].spines.values():
            spine.set_color(FRAME)
            spine.set_linewidth(0.65)
        if column == 0:
            axes[0, column].set_ylabel("节点编号")
        axes[1, column].fill_between(
            time,
            aggregate,
            1,
            color=CORAL,
            alpha=0.20,
            linewidth=0,
        )
        axes[1, column].plot(time, aggregate, color=BLUE, linewidth=1.8)
        axes[1, column].set_ylim(0, 1.03)
        axes[1, column].set_xlabel("归一化执行时间")
        axes[1, column].text(
            0.03,
            0.08,
            rf"$E_{{comp}}^P={100 * batch['compute_service_exposure']:.1f}\%$"
            "\n"
            rf"空闲面积 $={100 * batch['idle_area']:.1f}\%$",
            transform=axes[1, column].transAxes,
            fontsize=8.2,
            color=INK,
        )
        finish_axis(axes[1, column])
        if column == 0:
            axes[1, column].set_ylabel(r"聚合利用率 $u_{comp}(t)$")
    colorbar_axis = figure.add_axes((0.93, 0.56, 0.012, 0.29))
    colorbar = figure.colorbar(image, cax=colorbar_axis)
    colorbar.set_label("节点计算利用率", color=INK)
    colorbar.outline.set_edgecolor(FRAME)
    colorbar.outline.set_linewidth(0.6)
    colorbar.ax.tick_params(colors=MUTED, length=3, width=0.6)
    figure.subplots_adjust(
        left=0.075,
        right=0.91,
        bottom=0.12,
        top=0.90,
        hspace=0.18,
        wspace=0.20,
    )
    save(figure, output)


def _set_stage_ticks(axis):
    axis.set_xticks(
        (0, 1, 5, 10, 15, 20),
        ("0%", "1%", "5%", "10%", "15%", "20%"),
        rotation=32,
        ha="right",
    )
