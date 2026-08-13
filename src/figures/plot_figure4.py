from __future__ import annotations

from pathlib import Path
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from figure_style import (CONTRAST, GRID, NEUTRAL, PA, UA, add_zero_and_grid,
                          mm, panel_label, save_figure, set_style)

REPO = HERE.parents[1]
D2R = REPO
DATA = D2R / "data/figure_source_data"
OUT = D2R / "results/figures/Figure4_conditional_dose_response"
HEIGHT_MM = 136.0
WIDTH_MM = 180.0
EXPORT_FORMATS = (".svg", ".pdf", ".png", ".tiff")
RASTER_DPI = 600
plt.rcParams.update({"font.family": "Arial", "svg.fonttype": "none", "pdf.fonttype": 42})


def response_panel(ax, curves: pd.DataFrame, outcome: str, title: str, ylabel: str) -> None:
    for land, color, ls, marker in [("PA", PA, "-", "o"), ("UA", UA, (0, (5, 2)), "^")]:
        q = curves[(curves.outcome == outcome) & (curves.landscape_type == land)].sort_values("dose")
        x = q.dose.to_numpy(float)
        ax.fill_between(x, q.conf_low.to_numpy(float), q.conf_high.to_numpy(float),
                        color=color, alpha=0.13, lw=0)
        ax.plot(x, q.estimate.to_numpy(float), color=color, ls=ls, lw=1.45,
                marker=marker, markevery=12, ms=2.8, mec="white", mew=0.35, label=land)
    for x in [3, 10]:
        ax.axvline(x, color=NEUTRAL, lw=0.65, ls=(0, (2, 2)))
    add_zero_and_grid(ax)
    ax.set(xlabel="Cumulative event days", ylabel=ylabel, title=title)
    ax.legend(ncol=2, loc="best")


def main() -> None:
    set_style(2.0)
    support = pd.read_csv(DATA / "Figure3a.csv")
    curves = pd.read_csv(DATA / "Figure3bc.csv")
    contrasts = pd.read_csv(DATA / "Figure3d.csv").sort_values("latitude")
    shape = pd.read_csv(DATA / "Figure3d_shape.csv")

    fig, axs = plt.subplots(2, 2, figsize=(mm(WIDTH_MM), mm(HEIGHT_MM)))
    fig.subplots_adjust(left=17/WIDTH_MM, right=1-5/WIDTH_MM, bottom=10/HEIGHT_MM,
                        top=1-5/HEIGHT_MM, wspace=0.30, hspace=0.38)

    ax = axs[0, 0]
    bins = np.arange(0.5, support.dose.max() + 1.5, 1)
    for land, color in [("PA", PA), ("UA", UA)]:
        q = support[support.landscape_type == land]
        weights = q.analysis_weight / q.analysis_weight.sum()
        ax.hist(q.dose, bins=bins, weights=weights, histtype="step", lw=1.75,
                color=color, label=land, zorder=4)
    ax.set_ylim(0, 0.45)
    for x, label in [(3, "3 days"), (10, "10 days")]:
        ax.axvline(x, ymax=0.90, color=CONTRAST, lw=0.8, ls=(0, (3, 2)), zorder=2)
        ax.text(x, 0.438, label, ha="center", va="top", fontsize=8.5, fontweight="normal")
    ax.grid(axis="y", color=GRID, lw=0.45)
    ax.set_axisbelow(True)
    ax.set(xlabel="Cumulative event days", ylabel="Weighted fraction",
           title="Dose support near 35°N")
    ax.legend(ncol=2, loc="upper right")
    panel_label(ax, "a")

    response_panel(axs[0, 1], curves, "mean_anomaly_crossfit", "Signed SOS response",
                   "Change in signed anomaly (days)")
    panel_label(axs[0, 1], "b")
    response_panel(axs[1, 0], curves, "mean_abs_anomaly_crossfit", "Absolute SOS response",
                   "Change in absolute anomaly (days)")
    panel_label(axs[1, 0], "c")

    ax = axs[1, 1]
    y_lookup = {25.0: 4.0, 35.0: 3.0, 45.0: 1.0, 55.0: 0.0}
    ybase = contrasts.latitude.map(y_lookup).to_numpy(float)
    est = contrasts.estimate.to_numpy(float)
    specs = [
        ("Clustered", "conf_low", "conf_high", 0, CONTRAST, "D", True),
        ("5° block", "conf_low_5", "conf_high_5", -0.55, UA, "o", False),
        ("10° block", "conf_low_10", "conf_high_10", 0.55, PA, "s", True),
    ]
    for label, lo, hi, off, color, marker, filled in specs:
        xerr = np.vstack([est - contrasts[lo].to_numpy(float),
                          contrasts[hi].to_numpy(float) - est])
        ax.errorbar(est, ybase + off / 3, xerr=xerr, fmt=marker, color=color, ecolor=color,
                    lw=1.15, capsize=2.0, capthick=1.0, ms=3.8,
                    mfc=color if filled else "white", label=label)
    r = shape.iloc[0]
    ax.errorbar(r.estimate_linear, 2.0,
                xerr=[[r.estimate_linear - r.conf_low_linear],
                      [r.conf_high_linear - r.estimate_linear]],
                fmt="o", color=NEUTRAL, ecolor=NEUTRAL, lw=1.15, capsize=2.0,
                ms=3.8, mfc="white", mec=NEUTRAL, label="_nolegend_")
    ax.axvline(0, color=NEUTRAL, lw=0.7, ls=(0, (3, 3)), zorder=0)
    ax.grid(axis="x", color=GRID, lw=0.45, zorder=0)
    ax.set_axisbelow(True)
    ax.set_yticks([4, 3, 2, 1, 0], ["25°N spline", "35°N spline", "35°N linear",
                                    "45°N spline", "55°N spline"])
    ax.set_ylim(-0.4, 5.2)
    ax.set(xlabel="UA −PA absolute-anomaly contrast (days)",
           title="Spatial robustness and model-form sensitivity")
    ax.legend(ncol=3, loc="upper center", handlelength=1.3, columnspacing=0.6)
    panel_label(ax, "d")

    save_figure(fig, OUT)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()



