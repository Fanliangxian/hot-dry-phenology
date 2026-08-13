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
from figure_style import CONTRAST, GRID, PA, UA, mm, panel_label, save_figure, set_style

REPO = HERE.parents[1]
D2R = REPO
OUT = D2R / "results/figures/FigureS3_occurrence_sensitivity"
HEIGHT_MM = 82.0
WIDTH_MM = 180.0
EXPORT_FORMATS = (".svg", ".pdf", ".png", ".tiff")
RASTER_DPI = 600
plt.rcParams.update({"font.family": "Arial", "svg.fonttype": "none", "pdf.fonttype": 42})


def main() -> None:
    set_style(2.0)
    a = pd.read_csv(D2R / "data/figure_source_data/FigureS3a.csv")
    b = pd.read_csv(D2R / "data/figure_source_data/FigureS3b.csv")
    windows = sorted(a[["gap_days", "event_min_days"]].drop_duplicates().itertuples(index=False),
                     key=lambda r: (r.gap_days, r.event_min_days))
    labels = [f"g{int(r.gap_days)}/d{int(r.event_min_days)}" for r in windows]
    x = np.arange(len(windows))

    fig, axs = plt.subplots(1, 2, figsize=(mm(WIDTH_MM), mm(HEIGHT_MM)))
    fig.subplots_adjust(left=13/WIDTH_MM, right=1-5/WIDTH_MM, bottom=20/HEIGHT_MM,
                        top=1-8/HEIGHT_MM, wspace=0.24)
    for pheno, color, marker in [("SOS", UA, "o"), ("EOS", PA, "s")]:
        q = a[a.pheno_type == pheno].set_index(["gap_days", "event_min_days"])
        vals = [q.loc[(r.gap_days, r.event_min_days), "p_value_bh"] for r in windows]
        vals = np.clip(np.asarray(vals, dtype=float), np.finfo(float).tiny, 1.0)
        vals = -np.log10(vals)
        axs[0].plot(x, vals, color=color, marker=marker, lw=1.4, ms=4.0, label=pheno)
        qb = b[b.pheno_type == pheno].set_index(["gap_days", "event_min_days"])
        counts = [qb.loc[(r.gap_days, r.event_min_days), "robust_latitudes"] for r in windows]
        axs[1].plot(x, counts, color=color, marker=marker, lw=1.4, ms=4.0, label=pheno)

    axs[0].axhline(-np.log10(0.05), color=CONTRAST, lw=0.7, ls=(0, (3, 2)))
    axs[0].set_ylabel("−log10(BH-adjusted P)")
    axs[0].set_title("Global latitude-varying landscape test")
    axs[0].legend(loc="upper left")
    axs[1].set_ylabel("Latitudes robust at both spatial scales")
    axs[1].set_title("Local two-scale spatial robustness")
    axs[1].set_ylim(-0.2, 4.2)
    axs[1].set_yticks([0, 1, 2, 3, 4])
    for i, ax in enumerate(axs):
        ax.set_xticks(x, labels, rotation=35, ha="right")
        ax.set_xlabel("Window definition (gap/minimum duration, days)")
        ax.grid(axis="y", color=GRID, lw=0.45)
        ax.set_axisbelow(True)
        panel_label(ax, "ab"[i], x=-0.02)

    save_figure(fig, OUT)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()



