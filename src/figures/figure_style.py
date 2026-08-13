from __future__ import annotations

from pathlib import Path
import matplotlib as mpl

MM_PER_INCH = 25.4
WIDTH_MM = 180.0

PA = "#3F67C6"
UA = "#B82E6B"
CONTRAST = "#2E2E2E"
NEUTRAL = "#777777"
GRID = "#D9D9D9"
LIGHT = "#ECECEC"


def mm(value: float) -> float:
    return value / MM_PER_INCH


def set_style(font_offset: float = 2.0) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 7.3 + font_offset,
        "axes.labelsize": 7.5 + font_offset,
        "axes.titlesize": 8.0 + font_offset,
        "xtick.labelsize": 7.3 + font_offset,
        "ytick.labelsize": 7.3 + font_offset,
        "legend.fontsize": 6.8 + font_offset,
        "axes.linewidth": 0.7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "legend.frameon": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })


def panel_label(ax, label: str, *, x: float = -0.075, y: float = 1.015,
                font_offset: float = 2.0) -> None:
    ax.text(x, y, label, transform=ax.transAxes, ha="left", va="bottom",
            fontsize=11.5 + font_offset, fontweight="bold", clip_on=False)


def add_zero_and_grid(ax) -> None:
    ax.axhline(0, color=NEUTRAL, lw=0.7, ls=(0, (3, 3)), zorder=0)
    ax.grid(axis="y", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)


def save_figure(fig, output_stem: Path) -> None:
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    common = {"facecolor": "white", "edgecolor": "white"}
    fig.savefig(output_stem.with_suffix(".svg"), **common)
    fig.savefig(output_stem.with_suffix(".pdf"), **common)
    fig.savefig(output_stem.with_suffix(".png"), dpi=300, **common)
    fig.savefig(output_stem.with_suffix(".tiff"), dpi=600,
                pil_kwargs={"compression": "tiff_lzw"}, **common)


