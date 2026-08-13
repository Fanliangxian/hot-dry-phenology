from __future__ import annotations

from pathlib import Path
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from figure_style import (CONTRAST, GRID, NEUTRAL, PA, UA, add_zero_and_grid,
                          mm, panel_label, save_figure, set_style)

REPO = HERE.parents[1]
D2R = REPO
DATA = D2R / "data/figure_source_data"
BOOTSTRAP_DRAWS = DATA / "Figure5_resistance_bootstrap_draws.csv"
OUT = D2R / "results/figures/Figure5_ecological_resistance"
HEIGHT_MM = 190.0
WIDTH_MM = 180.0
EXPORT_FORMATS = (".svg", ".pdf", ".png", ".tiff")
RASTER_DPI = 600
plt.rcParams.update({"font.family": "Arial", "svg.fonttype": "none", "pdf.fonttype": 42})


def forest_curve_panel(ax, curves: pd.DataFrame, land: str) -> None:
    color = PA if land == "PA" else UA
    styles = {25: ":", 35: "-", 45: (0, (5, 2)), 55: (0, (4, 2, 1, 2))}
    for lat, ls in styles.items():
        q = curves[(curves.landscape_type == land) & (curves.latitude == lat)].sort_values("moderator_value")
        ax.plot(q.moderator_value, q.estimate, color=color, ls=ls, lw=1.4, label=f"{lat}°N")
    add_zero_and_grid(ax)
    ax.set_xlabel("Forest fraction")
    ax.set_title(f"{land}: forest-associated EOS resistance")
    ax.legend(ncol=2, loc="upper left")


def contrast_panel(ax, q: pd.DataFrame, title: str, ylabel: str, show_legend: bool) -> None:
    order = ["PA", "UA", "UA_minus_PA"]
    labels = ["PA", "UA", "UA −PA"]
    x = np.arange(3)
    q = q.set_index("landscape_type").loc[order].reset_index()
    est = q.estimate.to_numpy(float)
    specs = [
        ("Clustered 95% CI", "conf_low", "conf_high", 0.00, CONTRAST, "D", True),
        ("5° block", "conf_low_5", "conf_high_5", -0.14, UA, "o", False),
        ("10° block", "conf_low_10", "conf_high_10", 0.14, PA, "s", True),
    ]
    for label, lo, hi, off, color, marker, filled in specs:
        yerr = np.vstack([est - q[lo].to_numpy(float), q[hi].to_numpy(float) - est])
        ax.errorbar(x + off, est, yerr=yerr, fmt=marker, color=color, ecolor=color,
                    lw=1.15, capsize=2.0, capthick=1.0, ms=4.0,
                    mfc=color if filled else "white", label=label)
    add_zero_and_grid(ax)
    ax.set_xticks(x, labels)
    ax.set_ylabel(ylabel)
    ax.set_title(title, pad=3)
    if show_legend:
        bottom, top = ax.get_ylim()
        ax.set_ylim(bottom, top + 0.75)
        ax.legend(ncol=3, loc="upper center", bbox_to_anchor=(0.5, 0.99),
                  borderaxespad=0.0, handlelength=1.2, columnspacing=0.6)


def _side_half_violin(ax, values: np.ndarray, position: float, color: str,
                      side: str, width: float = 0.095) -> None:
    """Draw a category-scale half violin matching Figure 3's visual thickness."""
    violin = ax.violinplot([values], positions=[position], widths=width * 2,
                           showmeans=False, showmedians=False,
                           showextrema=False, points=80, bw_method="scott")
    body = violin["bodies"][0]
    body.set_facecolor(color)
    body.set_edgecolor(color)
    body.set_linewidth(0.45)
    body.set_alpha(0.34)
    vertices = body.get_paths()[0].vertices
    if side == "left":
        vertices[:, 0] = np.minimum(vertices[:, 0], position)
    else:
        vertices[:, 0] = np.maximum(vertices[:, 0], position)


def contrast_distribution_panel(ax, q: pd.DataFrame, draws: pd.DataFrame,
                                title: str, ylabel: str, show_legend: bool) -> None:
    order = ["PA", "UA", "UA_minus_PA"]
    labels = ["PA", "UA", "UA −PA"]
    x = np.arange(3, dtype=float)
    q = q.set_index("landscape_type").loc[order].reset_index()

    # Clustered model is the centered primary result.
    est = q.estimate.to_numpy(float)
    yerr = np.vstack([est - q.conf_low.to_numpy(float),
                      q.conf_high.to_numpy(float) - est])
    ax.errorbar(x, est, yerr=yerr, fmt="D", color=CONTRAST, ecolor=CONTRAST,
                lw=1.20, capsize=2.0, capthick=1.0, ms=4.2,
                mfc=CONTRAST, mec=CONTRAST, label="Clustered 95% CI", zorder=7)

    for degree, offset, color, marker, side, label in [
        (5, -0.16, UA, "o", "left", "5° spatial block"),
        (10, 0.16, PA, "s", "right", "10° spatial block"),
    ]:
        for i, landscape in enumerate(order):
            values = draws[(draws.landscape_type == landscape) &
                           (draws.block_degrees == degree)].value.to_numpy(float)
            position = x[i] + offset
            _side_half_violin(ax, values, position, color, side)
            median = float(np.median(values))
            low, high = np.quantile(values, [0.025, 0.975])
            ax.vlines(position, low, high, color=color, lw=1.05, zorder=5)
            ax.plot(position, median, marker=marker, color=color, ms=3.6,
                    mfc="white" if degree == 5 else color, mec=color,
                    mew=0.8, zorder=6)

    add_zero_and_grid(ax)
    ax.set_xticks(x, labels)
    ax.set_ylabel(ylabel)
    ax.set_title(title, pad=3)
    if show_legend:
        handles = [
            Line2D([0], [0], marker="D", color=CONTRAST, lw=1.2,
                   mfc=CONTRAST, mec=CONTRAST, label="Clustered 95% CI"),
            Line2D([0], [0], marker="o", color=UA, lw=1.05,
                   mfc="white", mec=UA, label="5° spatial block"),
            Line2D([0], [0], marker="s", color=PA, lw=1.05,
                   mfc=PA, mec=PA, label="10° spatial block"),
        ]
        bottom, top = ax.get_ylim()
        ax.set_ylim(bottom, top + 0.75)
        ax.legend(handles=handles, ncol=1, loc="upper right",
                  bbox_to_anchor=(1.045, 0.99), borderaxespad=0.0,
                  handlelength=1.2, labelspacing=0.3)


def support_panel(ax, support: pd.DataFrame) -> None:
    q = support[support.variable == "lc_forest_frac"].set_index("landscape_type").loc[["PA", "UA"]]
    for y, (land, row) in enumerate(q.iterrows()):
        color = PA if land == "PA" else UA
        ax.plot([row.q05, row.q95], [y, y], color=color, lw=2.2, solid_capstyle="round")
        ax.plot([row.q25, row.q75], [y, y], color=color, lw=7, alpha=0.28,
                solid_capstyle="butt")
        ax.plot(row.q50, y, "o", color=color, ms=5.2)
        ax.plot(row.weighted_mean, y, "D", mfc="white", mec=color, mew=1.0, ms=5.0)
    ax.set_yticks([0, 1], ["PA", "UA"])
    ax.set_ylim(1.35, -0.35)
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("Forest fraction")
    ax.set_title("Observed forest-fraction support")
    ax.grid(axis="x", color=GRID, lw=0.45)
    handles = [
        Line2D([0], [0], color="black", lw=2.2, label="5th–95th"),
        Line2D([0], [0], color="black", lw=7, alpha=0.28, label="25th–95th"),
        Line2D([0], [0], marker="o", color="black", lw=0, label="Median"),
        Line2D([0], [0], marker="D", mfc="white", mec="black", color="black", lw=0,
               label="Weighted mean"),
    ]
    ax.legend(handles=handles, ncol=2, loc="center", bbox_to_anchor=(0.62, 0.50),
              fontsize=7.7, columnspacing=0.8, handletextpad=0.5)


def precip_curve_panel(ax, curves: pd.DataFrame) -> None:
    for land, color, ls, marker in [("PA", PA, "-", "o"), ("UA", UA, (0, (5, 2)), "^")]:
        q = curves[curves.landscape_type == land].sort_values("moderator_value")
        x = q.moderator_value.to_numpy(float)
        ax.fill_between(x, q.conf_low.to_numpy(float), q.conf_high.to_numpy(float),
                        color=color, alpha=0.13, lw=0)
        ax.plot(x, q.estimate.to_numpy(float), color=color, ls=ls, lw=1.45,
                marker=marker, markevery=20, ms=2.8, mec="white", mew=0.35, label=land)
    for x, text in [(456, "Q25"), (857, "Q75")]:
        ax.axvline(x, color=NEUTRAL, lw=0.65, ls=(0, (2, 2)))
        ax.text(x, 0.97, text, transform=ax.get_xaxis_transform(), ha="center", va="top",
                color=NEUTRAL, fontsize=8.0)
    add_zero_and_grid(ax)
    ax.set_xlabel("Annual precipitation (mm)")
    ax.set_ylabel("Conditional SOS dose resistance (days)")
    ax.set_title("Precipitation-associated resistance at 35°N")
    ax.legend(ncol=2, loc="lower left")


def main() -> None:
    set_style(2.0)
    forest_curves = pd.read_csv(DATA / "Figure4ab.csv")
    forest_contrasts = pd.read_csv(DATA / "Figure4c.csv")
    support = pd.read_csv(DATA / "Figure4d.csv")
    precip_curves = pd.read_csv(DATA / "Figure4e.csv")
    precip_contrasts = pd.read_csv(DATA / "Figure4f.csv")
    bootstrap_draws = pd.read_csv(BOOTSTRAP_DRAWS)

    fig, axs = plt.subplots(3, 2, figsize=(mm(WIDTH_MM), mm(HEIGHT_MM)))
    fig.subplots_adjust(left=18/WIDTH_MM, right=1-5/WIDTH_MM, bottom=9/HEIGHT_MM,
                        top=1-5/HEIGHT_MM, wspace=0.22, hspace=0.42)

    forest_curve_panel(axs[0, 0], forest_curves, "PA")
    axs[0, 0].set_ylabel("EOS resistance (days)")
    panel_label(axs[0, 0], "a")
    forest_curve_panel(axs[0, 1], forest_curves, "UA")
    panel_label(axs[0, 1], "b")
    forest_low = float(forest_curves.conf_low.min())
    forest_high = float(forest_curves.conf_high.max())
    forest_pad = 0.06 * (forest_high - forest_low)
    axs[0, 0].set_ylim(forest_low - forest_pad, forest_high + forest_pad)
    axs[0, 1].set_ylim(forest_low - forest_pad, forest_high + forest_pad)

    contrast_distribution_panel(
        axs[1, 0], forest_contrasts,
        bootstrap_draws[bootstrap_draws.target == "forest_occurrence_EOS"],
        "Forest-associated resistance contrast",
        "Resistance change from\nforest fraction 0 to 0.5 (days)", True)
    panel_label(axs[1, 0], "c")
    support_panel(axs[1, 1], support)
    panel_label(axs[1, 1], "d")

    precip_curve_panel(axs[2, 0], precip_curves)
    panel_label(axs[2, 0], "e")
    contrast_distribution_panel(
        axs[2, 1], precip_contrasts,
        bootstrap_draws[bootstrap_draws.target == "precipitation_dose_SOS"],
        "Precipitation-associated resistance contrast",
        "Resistance change across\n401-mm IQR (days)", False)
    panel_label(axs[2, 1], "f")

    save_figure(fig, OUT)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()



