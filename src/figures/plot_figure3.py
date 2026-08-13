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
DATA_FILE = D2R / "data/figure_source_data/Figure2_SourceData.csv"
BOOTSTRAP_DRAWS_FILE = D2R / "data/figure_source_data/Figure3_spatial_bootstrap_draws.csv"
OUT = D2R / "results/figures/Figure3_latitude_occurrence"
HEIGHT_MM = 178.0
WIDTH_MM = 180.0
EXPORT_FORMATS = (".svg", ".pdf", ".png", ".tiff")
RASTER_DPI = 600
plt.rcParams.update({"font.family": "Arial", "svg.fonttype": "none", "pdf.fonttype": 42})


def curve_panel(ax, curves: pd.DataFrame, pheno: str) -> None:
    styles = {
        "event_effect_PA": (PA, "-", "o", "PA"),
        "event_effect_UA": (UA, (0, (5, 2)), "^", "UA"),
    }
    for contrast, (color, ls, marker, label) in styles.items():
        q = curves[(curves.pheno_type == pheno) & (curves.contrast == contrast)].sort_values("latitude")
        x, y = q.latitude.to_numpy(float), q.estimate.to_numpy(float)
        ax.fill_between(x, q.conf_low.to_numpy(float), q.conf_high.to_numpy(float),
                        color=color, alpha=0.13, lw=0)
        ax.plot(x, y, color=color, ls=ls, lw=1.45, marker=marker, markevery=20,
                ms=2.8, mec="white", mew=0.35, label=label)
    add_zero_and_grid(ax)


def contrast_panel(ax, curves: pd.DataFrame, blocks: pd.DataFrame, pheno: str) -> None:
    q = curves[(curves.pheno_type == pheno) &
               (curves.contrast == "UA_minus_PA_event_effect")].sort_values("latitude")
    x, y = q.latitude.to_numpy(float), q.estimate.to_numpy(float)
    ax.fill_between(x, q.conf_low.to_numpy(float), q.conf_high.to_numpy(float),
                    color=CONTRAST, alpha=0.12, lw=0, label="Clustered 95% CI")
    ax.plot(x, y, color=CONTRAST, lw=1.55, marker="D", markevery=20, ms=2.5,
            mec="white", mew=0.35, label="UA −PA")
    for degree, offset, color, marker, label in [
        (5, -0.28, UA, "o", "5° spatial block"),
        (10, 0.28, PA, "s", "10° spatial block"),
    ]:
        b = blocks[(blocks.pheno_type == pheno) & (blocks.block_degrees == degree)].sort_values("latitude")
        xx, yy = b.latitude.to_numpy(float) + offset, b.estimate.to_numpy(float)
        yerr = np.vstack([yy - b.conf_low.to_numpy(float), b.conf_high.to_numpy(float) - yy])
        ax.errorbar(xx, yy, yerr=yerr, fmt=marker, color=color, ecolor=color,
                    ms=3.1, lw=0.8, capsize=1.7,
                    mfc="white" if degree == 5 else color, mec=color, mew=0.7,
                    label=label, zorder=4)
    add_zero_and_grid(ax)


def window_panel(ax, sensitivity: pd.DataFrame) -> None:
    q = sensitivity.sort_values(["gap_days", "event_min_days"]).reset_index(drop=True)
    labels = [f"{int(r.gap_days)} / ≥{int(r.event_min_days)} d" for r in q.itertuples()]
    y = np.arange(len(q))[::-1]
    specs = [
        ("conf_low", "conf_high", 0.18, CONTRAST, "D", "Clustered"),
        ("conf_low_5", "conf_high_5", 0.00, UA, "o", "5° block"),
        ("conf_low_10", "conf_high_10", -0.18, PA, "s", "10° block"),
    ]
    for lo_col, hi_col, off, color, marker, label in specs:
        est = q.estimate.to_numpy(float)
        lo, hi = q[lo_col].to_numpy(float), q[hi_col].to_numpy(float)
        ax.errorbar(est, y + off, xerr=np.vstack([est - lo, hi - est]), fmt=marker,
                    color=color, ecolor=color, ms=3.1, lw=0.8, capsize=1.6,
                    mfc="white" if marker == "o" else color, mec=color, mew=0.7,
                    label=label, zorder=3)
    ax.axvline(0, color=NEUTRAL, lw=0.7, ls=(0, (3, 3)), zorder=0)
    ax.grid(axis="x", color=GRID, lw=0.45, zorder=0)
    ax.set_yticks(y, labels)
    ax.set_xlabel("UA −PA EOS association at 25°N (days)")
    ax.set_title("EOS at 25°N: event-window sensitivity (spatially robust: 2/6)", pad=5)
    ax.legend(loc="upper right", ncol=1, handletextpad=0.4, labelspacing=0.35)


def _half_violin(ax, values: np.ndarray, position: float, color: str,
                 width: float = 0.92) -> None:
    """Draw a narrow right-facing half violin for bootstrap draws."""
    violin = ax.violinplot([values], positions=[position], widths=width * 2,
                           showmeans=False, showmedians=False,
                           showextrema=False, points=80, bw_method="scott")
    body = violin["bodies"][0]
    body.set_facecolor(color)
    body.set_edgecolor(color)
    body.set_linewidth(0.45)
    body.set_alpha(0.34)
    vertices = body.get_paths()[0].vertices
    vertices[:, 0] = np.maximum(vertices[:, 0], position)


def contrast_panel_with_distributions(ax, curves: pd.DataFrame, blocks: pd.DataFrame,
                                      draws: pd.DataFrame, pheno: str) -> None:
    q = curves[(curves.pheno_type == pheno) &
               (curves.contrast == "UA_minus_PA_event_effect")].sort_values("latitude")
    x, y = q.latitude.to_numpy(float), q.estimate.to_numpy(float)
    ax.fill_between(x, q.conf_low.to_numpy(float), q.conf_high.to_numpy(float),
                    color=CONTRAST, alpha=0.12, lw=0, label="Clustered 95% CI")
    ax.plot(x, y, color=CONTRAST, lw=1.55, marker="D", markevery=20, ms=2.5,
            mec="white", mew=0.35, label="UA −PA")
    for degree, offset, color, marker, label in [
        (5, -1.35, UA, "o", "5° spatial block"),
        (10, 0.15, PA, "s", "10° spatial block"),
    ]:
        b = blocks[(blocks.pheno_type == pheno) &
                   (blocks.block_degrees == degree)].sort_values("latitude")
        for row in b.itertuples():
            values = draws[(draws.pheno_type == pheno) &
                           (draws.block_degrees == degree) &
                           (draws.latitude == row.latitude)].value.to_numpy(float)
            position = float(row.latitude) + offset
            _half_violin(ax, values, position, color)
            median = float(np.median(values))
            low, high = np.quantile(values, [0.025, 0.975])
            ax.vlines(position, low, high, color=color, lw=1.05, zorder=5)
            ax.plot(position, median, marker=marker, color=color, ms=3.2,
                    mfc="white" if degree == 5 else color, mec=color, mew=0.7,
                    zorder=6)
        ax.plot([], [], marker=marker, color=color, lw=1.05, ms=3.2,
                mfc="white" if degree == 5 else color, mec=color, label=label)
    add_zero_and_grid(ax)


def main() -> None:
    set_style(2.0)
    data = pd.read_csv(DATA_FILE)
    draws = pd.read_csv(BOOTSTRAP_DRAWS_FILE)
    curves = data[data.record_type == "primary_curve"].copy()
    blocks = data[data.record_type == "primary_spatial_interval"].copy()
    globals_ = data[data.record_type == "primary_global_test"].copy()
    sensitivity = data[data.record_type == "eos25_window_sensitivity"].copy()

    fig = plt.figure(figsize=(mm(WIDTH_MM), mm(HEIGHT_MM)))
    gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 0.84], left=19/WIDTH_MM,
                          right=1-5/WIDTH_MM, bottom=10/HEIGHT_MM, top=1-5/HEIGHT_MM,
                          wspace=0.10, hspace=0.34)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]),
            fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1]),
            fig.add_subplot(gs[2, :])]

    for i, pheno in enumerate(["SOS", "EOS"]):
        curve_panel(axes[i], curves, pheno)
        axes[i].set_title(f"{pheno}: event association by landscape", pad=3)
        axes[i].tick_params(labelbottom=False)
        if i == 0:
            axes[i].set_ylabel("Signed timing association (days)")
        panel_label(axes[i], "ab"[i])

        ax = axes[i + 2]
        contrast_panel_with_distributions(ax, curves, blocks, draws, pheno)
        ax.set_title(f"{pheno}: landscape contrast", pad=3)
        ax.set_xlabel("Latitude (°N)")
        if i == 0:
            ax.set_ylabel("UA −PA association (days)")
        p = float(globals_[globals_.pheno_type == pheno].p_value_bh.iloc[0])
        ptxt = f"BH-adjusted global P = {p:.3f}" if p >= 0.001 else "BH-adjusted global P < 0.001"
        ax.text(0.98, 0.04, ptxt, transform=ax.transAxes, ha="right", va="bottom",
                fontsize=8.5, color=NEUTRAL)
        panel_label(ax, "cd"[i])

    for ax in axes[:4]:
        ax.set_xlim(23.5, 59.5)
        ax.set_xticks([25, 35, 45, 55])
    effect_lo = min(curves[curves.contrast.isin(["event_effect_PA", "event_effect_UA"])].conf_low)
    effect_hi = max(curves[curves.contrast.isin(["event_effect_PA", "event_effect_UA"])].conf_high)
    axes[0].set_ylim(effect_lo - 1, effect_hi + 1)
    axes[1].set_ylim(effect_lo - 1, effect_hi + 1)
    contrast_lo = min(curves[curves.contrast == "UA_minus_PA_event_effect"].conf_low.min(), blocks.conf_low.min())
    contrast_hi = max(curves[curves.contrast == "UA_minus_PA_event_effect"].conf_high.max(), blocks.conf_high.max())
    for ax in axes[2:4]:
        ax.set_ylim(contrast_lo - 1, contrast_hi + 1)

    axes[0].legend(loc="upper left", ncol=2, handlelength=2.2, columnspacing=0.8)
    handles, labels = axes[2].get_legend_handles_labels()
    order = [1, 0, 2, 3]
    axes[2].legend([handles[i] for i in order], [labels[i] for i in order], loc="upper left",
                   ncol=2, handlelength=2.2, columnspacing=0.7)
    window_panel(axes[4], sensitivity)
    panel_label(axes[4], "e", x=-0.050, y=1.02)

    save_figure(fig, OUT)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()



