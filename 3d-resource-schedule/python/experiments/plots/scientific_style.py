"""Shared visual language for report-quality scientific figures."""

from pathlib import Path

import matplotlib.pyplot as plt

INK = "#172A3A"
MUTED = "#667481"
GRID = "#D9E0E6"
FRAME = "#AAB5BF"
PAPER = "#FFFFFF"

BLUE = "#356A92"
TEAL = "#2A9D8F"
CORAL = "#D96C4F"
GOLD = "#D6A53A"
PURPLE = "#7566A8"
SLATE = "#71808E"

BANDWIDTH_STYLE = {
    "0.5": (BLUE, "o"),
    "2.0": (TEAL, "s"),
    "8.0": (CORAL, "^"),
}


def configure() -> None:
    plt.rcParams.update(
        {
            "font.family": ("Noto Sans CJK SC", "DejaVu Sans"),
            "font.size": 9.5,
            "font.weight": "regular",
            "axes.titlesize": 10.5,
            "axes.titleweight": "normal",
            "axes.labelsize": 9.5,
            "axes.labelcolor": INK,
            "axes.edgecolor": FRAME,
            "axes.linewidth": 0.7,
            "axes.facecolor": PAPER,
            "figure.facecolor": PAPER,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "legend.fontsize": 8.5,
            "text.color": INK,
            "grid.color": GRID,
            "grid.linewidth": 0.55,
            "grid.alpha": 0.9,
            "lines.solid_capstyle": "round",
            "lines.solid_joinstyle": "round",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def finish_axis(axis, *, grid: str | None = "y") -> None:
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["left"].set_color(FRAME)
    axis.spines["bottom"].set_color(FRAME)
    axis.tick_params(length=3, width=0.7, color=FRAME)
    if grid is not None:
        axis.grid(axis=grid)
        axis.set_axisbelow(True)


def save(figure, output: Path) -> None:
    for suffix in (".png", ".pdf"):
        figure.savefig(
            output.with_suffix(suffix),
            dpi=320,
            bbox_inches="tight",
            facecolor=PAPER,
        )
    plt.close(figure)
