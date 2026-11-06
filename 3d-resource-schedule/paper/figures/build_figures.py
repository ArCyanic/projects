"""Build compact, print-sized data figures and editable DAC architecture diagrams."""

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FormatStrFormatter, MaxNLocator

HERE = Path(__file__).resolve().parent
NAVY = "#254E70"
BLUE = "#2C7FB8"
LIGHT = "#DDEAF3"
GRAY = "#8B959E"
AMBER = "#D3A14A"
INK = "#202B33"
RULE = "#D7DEE4"
WHITE = "#FFFFFF"
PALE = "#F4F7FA"
for font_path in (HERE.parents[1] / "assets/fonts").glob("LibertinusSerif-*.otf"):
    font_manager.fontManager.addfont(font_path)
plt.rcParams.update(
    {
        "font.family": ["Libertinus Serif"],
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8.5,
        "legend.fontsize": 7.3,
        "xtick.labelsize": 7.3,
        "ytick.labelsize": 7.3,
        "axes.linewidth": 0.65,
        "axes.edgecolor": GRAY,
        "text.color": INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "savefig.facecolor": "white",
        "axes.unicode_minus": False,
    }
)


def finish(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=RULE, linewidth=0.45)
    ax.set_axisbelow(True)
    ax.tick_params(length=2.4, width=0.65)


def save(fig, name):
    fig.savefig(HERE / f"{name}.pdf")
    fig.savefig(HERE / f"{name}.png", dpi=220)
    plt.close(fig)


def main_results():
    plot_main_results(DATA["main"], HERE / "04-main-results")


def plot_main_results(main, output):
    """Render the shared single-column selected-deployment performance figure."""
    targets = (
        ("Decode speed", None),
        ("T32 throughput", "32"),
        ("T128 throughput", "128"),
        ("T512 throughput", "512"),
    )
    with plt.style.context("default", after_reset=True):
        plt.rcParams.update(
            {
                "font.family": ["Libertinus Serif"],
                "font.size": 6.6,
                "axes.labelsize": 6.6,
                "xtick.labelsize": 6.3,
                "ytick.labelsize": 6.3,
                "axes.titlesize": 7.2,
                "axes.edgecolor": GRAY,
                "axes.linewidth": 0.65,
                "text.color": INK,
                "axes.labelcolor": INK,
                "xtick.color": INK,
                "ytick.color": INK,
                "figure.facecolor": WHITE,
                "savefig.facecolor": WHITE,
                "axes.unicode_minus": False,
                "pdf.fonttype": 42,
            }
        )
        fig, axs = plt.subplots(4, 3, figsize=(3.36, 3.55), sharex=True, sharey="row")
        limits = [[] for _ in targets]
        for col, bw in enumerate(("0.5", "2.0", "8.0")):
            axs[0, col].set_title(f"{float(bw):g} GB/s", pad=17)
            for profile, color, marker, ls in (
                ("planar", NAVY, "o", "-"),
                ("vertical", AMBER, "s", "--"),
            ):
                entry = main[profile][bw]
                baseline = entry["baseline"]
                points = entry["selected"]
                budgets = [point["budget"] for point in points]
                anchors = [point["anchor"] for point in points]
                track = 1.17 if profile == "planar" else 1.07
                ax = axs[0, col]
                ax.text(
                    -0.06,
                    track + 0.026,
                    "P" if profile == "planar" else "V",
                    transform=ax.transAxes,
                    ha="right",
                    va="center",
                    fontsize=5.7,
                )
                start = 0
                for stop in range(1, len(anchors) + 1):
                    if stop == len(anchors) or anchors[stop] != anchors[start]:
                        fill = (
                            LIGHT if anchors[start] == "compute-balanced" else "#F2DFB9"
                        )
                        ax.add_patch(
                            Rectangle(
                                (start - 0.5, track),
                                stop - start,
                                0.055,
                                transform=ax.get_xaxis_transform(),
                                facecolor=fill,
                                edgecolor=GRAY,
                                linewidth=0.3,
                                clip_on=False,
                            )
                        )
                        start = stop
                for row, (label, token_count) in enumerate(targets):
                    base = (
                        baseline["decode"]["mean_ns"]
                        if token_count is None
                        else baseline["prefill"][token_count]["mean_ns"]
                    )
                    values = [
                        point["decode"]["mean_ns"]
                        if token_count is None
                        else point["prefill"][token_count]["mean_ns"]
                        for point in points
                    ]
                    ratios = base / np.asarray(values)
                    limits[row].extend(ratios)
                    axs[row, col].plot(
                        budgets,
                        ratios,
                        color=color,
                        linestyle=ls,
                        linewidth=0.9,
                        marker=marker,
                        markersize=2.0,
                        markerfacecolor="white",
                        markeredgewidth=0.5,
                        markevery=4,
                    )
                    if col == 0:
                        axs[row, col].set_ylabel(label, labelpad=3)
            for row in range(4):
                ax = axs[row, col]
                ax.set_xlim(-0.5, 20.5)
                ax.set_xticks((0, 10, 20))
                ax.axhline(1, color=GRAY, linewidth=0.45, linestyle=(0, (2, 2)))
                ax.yaxis.set_major_locator(MaxNLocator(nbins=3))
                ax.yaxis.set_major_formatter(FormatStrFormatter("%.2f"))
                finish(ax)
        for row, values in enumerate(limits):
            lower, upper = min(1, min(values)), max(1, max(values))
            margin = max(0.006, 0.10 * (upper - lower))
            axs[row, 0].set_yticks(
                (1.0, 1.1, 1.2, 1.3) if row == 0 else (1.0, 1.05, 1.1, 1.15)
            )
            axs[row, 0].set_ylim(lower - margin, upper + margin)
        fig.legend(
            handles=[
                Line2D(
                    [],
                    [],
                    color=NAVY,
                    marker="o",
                    markersize=2.5,
                    markerfacecolor="white",
                    label="Planar",
                ),
                Line2D(
                    [],
                    [],
                    color=AMBER,
                    linestyle="--",
                    marker="s",
                    markersize=2.5,
                    markerfacecolor="white",
                    label="Vertical",
                ),
                Patch(facecolor=LIGHT, edgecolor=GRAY, label="Balanced"),
                Patch(facecolor="#F2DFB9", edgecolor=GRAY, label="Hypergraph"),
            ],
            loc="upper center",
            bbox_to_anchor=(0.55, 0.997),
            ncol=4,
            fontsize=6.2,
            frameon=False,
            handlelength=1.4,
            handletextpad=0.35,
            columnspacing=0.9,
        )
        fig.supxlabel("Additional replica budget (%)", fontsize=7, y=0.012)
        fig.subplots_adjust(
            left=0.155, right=0.987, bottom=0.105, top=0.83, hspace=0.34, wspace=0.26
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output.with_suffix(".pdf"))
        fig.savefig(output.with_suffix(".png"), dpi=320)
        plt.close(fig)


def capacity_mechanisms():
    curves = DATA["resource_diagnostics"]["planar_budget_curves"]
    with plt.rc_context({"font.family": "STIXGeneral", "mathtext.fontset": "stix"}):
        fig = plt.figure(figsize=(7.05, 1.75))
        fig.text(0.025, 0.925, "(a) Prefill: time above fixed work", fontsize=8.5)
        fig.text(0.535, 0.925, "(b) Decode: variable path time", fontsize=8.5)
        fig.text(0.975, 0.925, "Planar", ha="right", fontsize=7.5)
        prefill_ax = fig.add_axes((0.065, 0.25, 0.405, 0.47))
        decode_ax = fig.add_axes((0.565, 0.25, 0.405, 0.47))
        colors = (AMBER, BLUE, GRAY)
        for group, bandwidth in enumerate(("0.5", "2.0")):
            points = curves[bandwidth]
            positions = np.arange(len(points)) + 4 * group
            values = []
            for point in points:
                prefill = point["prefill"]["512"]
                space = prefill["optimization_space"]
                mean = space["mean_compute_work_ns"]
                compute = space["peak_compute_work_ns"]
                network = space["peak_communication_work_ns"]
                values.append((
                    compute - mean,
                    max(network - compute, 0),
                    prefill["makespan_ns"] - max(compute, network),
                ))
            bottom = np.zeros(len(points))
            for component, color in zip(np.asarray(values).T / 1e6, colors, strict=True):
                prefill_ax.bar(positions, component, bottom=bottom, width=0.62,
                               color=color, edgecolor=WHITE, linewidth=0.35, zorder=2)
                bottom += component
            prefill_ax.text(positions.mean(), 1.06, f"{float(bandwidth):g} GB/s",
                            transform=prefill_ax.get_xaxis_transform(),
                            ha="center", fontsize=7.5)
        average_ms = curves["2.0"][0]["prefill"]["512"]["optimization_space"]["mean_compute_work_ns"] / 1e6
        prefill_ax.text(0.97, 0.87, rf"$\bar W={average_ms:.2f}$ ms",
                        transform=prefill_ax.transAxes, ha="right", fontsize=7.5)
        prefill_ax.set_ylim(0, 40)
        prefill_ax.set_ylabel("T512 excess time (ms)", labelpad=3)
        prefill_ax.yaxis.set_major_locator(MaxNLocator(4))
        for group, bandwidth in enumerate(("0.5", "8.0")):
            points = curves[bandwidth]
            positions = np.arange(len(points)) + 4 * group
            initial_latency = sum(points[0]["decode_components_ns"].values())
            bottom = np.zeros(len(points))
            for field, color in zip(
                ("node_serialization_ns", "mesh_service_ns", "collective_contention_ns"),
                colors, strict=True,
            ):
                component = np.asarray([point["decode_components_ns"][field] for point in points])
                component = 100 * component / initial_latency
                decode_ax.bar(positions, component, bottom=bottom, width=0.62,
                              color=color, edgecolor=WHITE, linewidth=0.35, zorder=2)
                bottom += component
            decode_ax.text(positions.mean(), 1.06, f"{float(bandwidth):g} GB/s",
                           transform=decode_ax.get_xaxis_transform(),
                           ha="center", fontsize=7.5)
        decode_ax.set_ylim(0, 100)
        decode_ax.set_ylabel("Variable Decode time\n(% of 0% latency)", labelpad=3)
        decode_ax.yaxis.set_major_locator(MaxNLocator(4))
        for ax in (prefill_ax, decode_ax):
            ax.set_xticks((0, 1, 2, 4, 5, 6), ("0", "5", "20", "0", "5", "20"))
            ax.set_xlabel("Replica budget (%)", labelpad=2)
            ax.set_xlim(-0.7, 6.7)
            ax.axvline(3, color=RULE, linewidth=0.65)
            ax.grid(axis="y", color=RULE, linewidth=0.5, zorder=0)
            finish(ax)
        for center, labels in (
            (0.27, ("Node skew", "Link excess", "Remainder")),
            (0.77, ("Serial", "Mesh", "Wait")),
        ):
            fig.legend(
                handles=[Patch(facecolor=color, label=label)
                         for color, label in zip(colors, labels, strict=True)],
                loc="upper center", bbox_to_anchor=(center, 0.88),
                ncol=3, frameon=False, handlelength=0.9,
                columnspacing=1.0, borderaxespad=0,
            )
        save(fig, "05-capacity-mechanisms")


def decode_analysis():
    mapping = MECHANISMS["single_copy_mapping"]
    cases = {
        (
            row["hardware_profile"],
            row["layout_bandwidth_GBps"],
            row["evaluation_bandwidth_GBps"],
        ): row["mean_ns"]
        for row in mapping["cases"]
    }
    bandwidths = (0.5, 2.0, 8.0)
    matrices = [
        np.array(
            [
                [
                    100 * (cases[profile, layout, evaluation] / cases[profile, evaluation, evaluation] - 1)
                    for evaluation in bandwidths
                ]
                for layout in bandwidths
            ]
        )
        for profile in ("planar", "vertical")
    ]
    spatial = mapping["spatial"]
    colors = LinearSegmentedColormap.from_list("mechanism-blue", [WHITE, LIGHT, BLUE, NAVY])
    latency_norm = Normalize(0, 5 * np.ceil(max(matrix.max() for matrix in matrices) / 5))
    node_norm = Normalize(0, 0.4)
    maximum_packets = max(
        max(row["tree_packets_per_link_per_layer"]) for row in spatial["cases"]
    )
    with plt.rc_context({"font.family": "STIXGeneral", "mathtext.fontset": "stix"}):
        fig = plt.figure(figsize=(7.05, 1.75))
        fig.text(0.025, 0.925, "(a) Cross-bandwidth replay", fontsize=8.5)
        fig.text(0.465, 0.925, "(b) Coactivation and tree traffic", fontsize=8.5)
        fig.text(0.97, 0.925, "Planar · evaluation at 2 GB/s", ha="right", fontsize=7.5)
        for index, (matrix, title) in enumerate(zip(matrices, ("Planar", "Vertical"), strict=True)):
            ax = fig.add_axes((0.075 + index * 0.175, 0.42, 0.14, 0.38))
            image = ax.imshow(matrix, cmap=colors, norm=latency_norm, interpolation="nearest")
            ax.set_title(title, pad=3)
            ax.set_xticks(range(3), ["0.5", "2", "8"])
            ax.set_yticks(range(3), ["0.5", "2", "8"])
            ax.tick_params(length=0, pad=3)
            for row in range(3):
                for column in range(3):
                    value = matrix[row, column]
                    ax.text(column, row, f"{value:.1f}", ha="center", va="center",
                            fontsize=7.5, color=WHITE if value > 0.55 * latency_norm.vmax else INK)
            ax.set_xticks(np.arange(-0.5, 3), minor=True)
            ax.set_yticks(np.arange(-0.5, 3), minor=True)
            ax.grid(which="minor", color=WHITE, linewidth=1.2)
            ax.tick_params(which="minor", length=0)
            for spine in ax.spines.values():
                spine.set_visible(False)
        fig.text(0.235, 0.27, "Evaluation BW (GB/s)", ha="center", fontsize=7.5)
        fig.text(0.018, 0.61, "Mapping BW (GB/s)", rotation=90, va="center", fontsize=7.5)
        colorbar = fig.colorbar(image, cax=fig.add_axes((0.085, 0.19, 0.285, 0.03)), orientation="horizontal")
        colorbar.set_label("Latency change vs. matched (%)", fontsize=7.3, labelpad=2)
        colorbar.ax.tick_params(length=2, width=0.5, labelsize=7)
        colorbar.outline.set_visible(False)
        for index, row in enumerate(spatial["cases"]):
            ax = fig.add_axes((0.475 + index * 0.255, 0.355, 0.225, 0.46))
            extra = np.asarray(row["node_extra_experts_per_layer"])
            packets = np.asarray(row["tree_packets_per_link_per_layer"])
            for (source, destination), flow in zip(spatial["links"], packets, strict=True):
                y0, x0 = divmod(source, 4)
                y1, x1 = divmod(destination, 4)
                ax.plot((x0, x1), (y0, y1), color="#9AB3BF",
                        linewidth=0.3 + 2.8 * flow / maximum_packets, zorder=1)
            nodes = ax.scatter(
                np.arange(16) % 4, np.arange(16) // 4,
                c=extra, cmap=colors, norm=node_norm, s=100,
                edgecolors=RULE, linewidths=0.6, zorder=2,
            )
            ax.set_title(f"Mapped at {row['layout_bandwidth_GBps']:g} GB/s", fontsize=8, pad=3)
            ax.set_xlim(-0.35, 3.35)
            ax.set_ylim(3.35, -0.35)
            ax.set_aspect("equal")
            ax.axis("off")
            fig.text(
                0.5875 + index * 0.255, 0.33,
                f"Per layer: {extra.sum():.2f} extra; {packets.sum():.2f} packet-hops",
                ha="center", va="top", fontsize=7.3,
            )
        colorbar = fig.colorbar(nodes, cax=fig.add_axes((0.49, 0.19, 0.225, 0.03)), orientation="horizontal")
        colorbar.set_ticks((0, 0.2, 0.4))
        colorbar.set_label("Extra experts / node / layer", fontsize=7.2, labelpad=2)
        colorbar.ax.tick_params(length=2, width=0.5, labelsize=7)
        colorbar.outline.set_visible(False)
        legend = fig.add_axes((0.765, 0.085, 0.21, 0.12))
        legend.axis("off")
        for y, value in ((0.72, 0.5), (0.22, 1.0)):
            legend.plot((0.02, 0.28), (y, y), color="#9AB3BF",
                        linewidth=0.3 + 2.8 * value / maximum_packets)
            legend.text(0.36, y, f"{value:g} packets / layer", va="center", fontsize=7.1)
        legend.set_xlim(0, 1)
        legend.set_ylim(0, 1)
        save(fig, "05-decode-analysis")


def scheduling_results():
    with plt.rc_context({"font.family": "STIXGeneral", "mathtext.fontset": "stix"}):
        fig = plt.figure(figsize=(7.05, 1.75))
        fig.text(0.025, 0.925, "(a) Decode decision costs", fontsize=8.5)
        fig.text(0.49, 0.925, "(b) Prefill · Planar, 2 GB/s, T128", fontsize=8.5)
        ax = fig.add_axes((0.075, 0.25, 0.345, 0.55))
        points = []
        for report in MECHANISMS["scheduling"]:
            profile = report["hardware_profile"]
            bandwidth = report["link_bandwidth_GBps"]
            baseline, root, joint = report["decode"]["stages"]
            before = baseline["components_ns"]
            coordinates = []
            for stage in (root, joint):
                after = stage["components_ns"]
                network = 100 * (
                    after["mesh_service_ns"] + after["collective_contention_ns"]
                    - before["mesh_service_ns"] - before["collective_contention_ns"]
                ) / baseline["mean_ns"]
                serial = 100 * (
                    after["node_serialization_ns"] - before["node_serialization_ns"]
                ) / baseline["mean_ns"]
                coordinates.append((network, serial))
            color, marker = (NAVY, "o") if profile == "planar" else (AMBER, "^")
            ax.annotate("", xy=coordinates[1], xytext=coordinates[0],
                        arrowprops={"arrowstyle": "-|>", "color": color, "lw": 1.1,
                                    "mutation_scale": 7, "shrinkA": 4, "shrinkB": 4}, zorder=3)
            for index, (x, y) in enumerate(coordinates):
                ax.scatter(x, y, s=24, marker=marker, edgecolors=color,
                           facecolors=WHITE if index == 0 else color, linewidths=0.9, zorder=4)
                points.append((x, y))
            offset = (4, 4) if profile == "planar" else (4, -4)
            ax.annotate(f"{bandwidth:g}", coordinates[1], xytext=offset,
                        textcoords="offset points", fontsize=7, color=color)
        coordinates = np.asarray(points + [(0, 0)])
        ax.set_xlim(coordinates[:, 0].min() - 4, coordinates[:, 0].max() + 7)
        ax.set_ylim(coordinates[:, 1].min() - 5, coordinates[:, 1].max() + 6)
        x = np.asarray(ax.get_xlim())
        for reduction in (-10, -20, -30, -40):
            ax.plot(x, reduction - x, color=RULE, linewidth=0.6, linestyle=":", zorder=0)
        for x_label, y_label, label in ((-29, 9, "−20%"), (-25, -15, "−40%")):
            ax.text(x_label, y_label, label, color=GRAY, fontsize=6.8, rotation=-21,
                    ha="center", va="center", bbox={"facecolor": WHITE, "edgecolor": "none", "pad": 0.15})
        ax.scatter(0, 0, marker="+", c=INK, s=28, linewidths=0.8, zorder=5)
        ax.axhline(0, color=GRAY, linewidth=0.5)
        ax.axvline(0, color=GRAY, linewidth=0.5)
        ax.set_xlabel("Network time change (%)", labelpad=3)
        ax.set_ylabel("Serial time change (%)", labelpad=3)
        finish(ax)
        ax.grid(False)
        ax.xaxis.set_major_locator(MaxNLocator(5))
        ax.yaxis.set_major_locator(MaxNLocator(5))
        fig.legend(
            handles=[
                Line2D([], [], marker="o", color=NAVY, lw=1, markersize=4, label="Planar"),
                Line2D([], [], marker="^", color=AMBER, lw=1, markersize=4, label="Vertical"),
            ],
            loc="upper left", bbox_to_anchor=(0.24, 0.985), ncol=2, frameon=False,
            handlelength=1.2, columnspacing=1.2, borderaxespad=0,
        )
        fig.text(0.075, 0.83, "Hollow: root-only → filled: joint; labels: GB/s", fontsize=7)
        timeline = MECHANISMS["prefill_timeline"]
        end_ms = timeline["time_edges_ns"][-1] / 1e6
        colors = LinearSegmentedColormap.from_list("node-busy", [WHITE, LIGHT, BLUE, NAVY])
        for index, row in enumerate(timeline["cases"]):
            bottom = 0.52 if index == 0 else 0.22
            heatmap = fig.add_axes((0.52, bottom, 0.345, 0.20))
            values = np.asarray(row["node_utilization"])
            image = heatmap.imshow(
                values, origin="lower", aspect="auto", interpolation="nearest",
                extent=(0, end_ms, -0.5, 15.5), cmap=colors, vmin=0, vmax=1,
            )
            finish_ms = row["makespan_ns"] / 1e6
            work = np.asarray(row["node_compute_work_ns"]) / 1e6
            name = "Round-robin" if index == 0 else "Cumulative work"
            heatmap.set_title(f"{name}   $J_P$={finish_ms:.2f} ms   $W_C$={work.max():.2f} ms",
                              loc="left", fontsize=7.4, pad=3)
            heatmap.axvline(finish_ms, color=INK, linewidth=0.6)
            if finish_ms < end_ms:
                heatmap.add_patch(Rectangle(
                    (finish_ms, -0.5), end_ms - finish_ms, 16,
                    facecolor=PALE, edgecolor=RULE, linewidth=0, hatch="////",
                ))
            heatmap.set_yticks((0, 7, 15))
            heatmap.set_ylabel("Node", labelpad=2, fontsize=7.5)
            heatmap.tick_params(length=2, width=0.5, pad=2, labelsize=7)
            heatmap.set_xlim(0, end_ms)
            heatmap.set_xticks((0, 20, 40, 60))
            if index == 0:
                heatmap.tick_params(labelbottom=False)
            else:
                heatmap.set_xlabel("Time (ms)", fontsize=7.5, labelpad=2)
            for spine in heatmap.spines.values():
                spine.set_color(RULE)
                spine.set_linewidth(0.5)
            marginal = fig.add_axes((0.90, bottom, 0.065, 0.20))
            marginal.barh(np.arange(16), work / work.mean(), height=0.72,
                          color=GRAY if index == 0 else NAVY, linewidth=0)
            marginal.axvline(1, color=AMBER, linewidth=0.7, linestyle="--")
            marginal.set_ylim(-0.5, 15.5)
            marginal.set_xlim(0, 1.2)
            marginal.set_xticks((1,), ["1"])
            marginal.tick_params(axis="x", length=2, pad=2, labelsize=7)
            marginal.set_yticks(())
            for spine in marginal.spines.values():
                spine.set_visible(False)
        fig.text(0.9325, 0.785, "Work / mean", ha="center", va="top", fontsize=7.2)
        colorbar = fig.colorbar(
            image, cax=fig.add_axes((0.81, 0.895, 0.155, 0.022)), orientation="horizontal"
        )
        colorbar.set_ticks((0, 0.5, 1))
        colorbar.ax.tick_params(length=2, width=0.5, labelsize=6.8, pad=1)
        colorbar.outline.set_visible(False)
        fig.text(0.8875, 0.94, "Node busy fraction", ha="center", fontsize=7)
        save(fig, "06-scheduling-results")


def cross_model_results():
    fig, axs = plt.subplots(2, 1, figsize=(3.36, 1.85), sharex=True, sharey=True)
    for i, (model, color) in enumerate(zip(CROSS_MODEL["models"], (NAVY, BLUE, LIGHT))):
        for ax, profile in zip(axs, ("planar", "vertical")):
            entry = model["profiles"][profile]
            gains = []
            for metric in ("decode", "32", "128", "512"):
                base = entry["baseline"]
                selected = entry["selected"]
                if metric == "decode":
                    base, selected = base["decode"], selected["decode"]
                else:
                    base, selected = (
                        base["prefill"][metric],
                        selected["prefill"][metric],
                    )
                gains.append(base["mean_ns"] / selected["mean_ns"])
            bars = ax.bar(
                np.arange(4) + (i - 1) * 0.25,
                gains,
                0.23,
                color=color,
                edgecolor=NAVY,
                linewidth=0.4,
                zorder=3,
                label=model["name"],
            )
            ax.bar_label(
                bars, fmt="%.2f", padding=8 if i == 1 else 1.5, fontsize=7, color=INK
            )
    for ax, profile in zip(axs, ("Planar", "Vertical")):
        ax.set_title(profile, loc="left", pad=2, fontsize=8)
        ax.set_xticks(np.arange(4), ["Decode", "T32", "T128", "T512"])
        ax.set_yticks((1.0, 1.1, 1.2, 1.3))
        ax.yaxis.set_major_formatter(FormatStrFormatter("%.1f"))
        ax.tick_params(labelsize=7)
        finish(ax)
    heights = [bar.get_height() for ax in axs for bar in ax.patches]
    low, high = min(1.0, min(heights)), max(heights)
    span = high - low
    axs[0].set_ylim(low - 0.10 * span, high + 0.55 * span)
    for ax in axs:
        ax.axhline(1, color=GRAY, linewidth=0.5, linestyle="--")
    fig.supylabel("Normalized speed / throughput", fontsize=7.5, x=0.008)
    handles, labels = axs[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.53, 1.008),
        ncol=3,
        frameon=False,
        columnspacing=0.7,
        handlelength=1,
        handletextpad=0.3,
        fontsize=7,
    )
    fig.subplots_adjust(left=0.145, right=0.985, bottom=0.14, top=0.80, hspace=0.45)
    save(fig, "07-cross-model-results")


def export_diagrams():
    """Export the editable architecture sources with embedded diagram XML."""
    executable = "/Applications/draw.io.app/Contents/MacOS/draw.io"
    for name in ("01-framework", "02-hardware", "03-mapping-scheduling"):
        source = HERE / f"{name}.drawio"
        for suffix in ("pdf", "svg", "png"):
            subprocess.run(
                [
                    executable,
                    "-x",
                    "-f",
                    suffix,
                    "-e",
                    *(["-s", "2"] if suffix == "png" else []),
                    "--crop",
                    "-b",
                    "2",
                    "-o",
                    str(HERE / f"{name}.drawio.{suffix}"),
                    str(source),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-only", action="store_true", help="Update Figures 4–7 without draw.io."
    )
    args = parser.parse_args()
    DATA = json.loads((HERE.parent / "data/results-20pct.json").read_text())
    CROSS_MODEL = json.loads(
        (HERE.parents[1] / "artifacts/results/cross-model-20pct.json").read_text()
    )
    MECHANISMS = json.loads((HERE.parent / "data/mechanisms.json").read_text())
    main_results()
    decode_analysis()
    capacity_mechanisms()
    scheduling_results()
    cross_model_results()
    if not args.data_only:
        export_diagrams()
    print("Updated paper/figures/")
