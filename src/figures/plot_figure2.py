from __future__ import annotations

from pathlib import Path
import os
import sys
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize, TwoSlopeNorm
from matplotlib.cm import ScalarMappable
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from figure_style import CONTRAST, GRID, PA, UA, mm, set_style

REPO = HERE.parents[1]
DATA = REPO / "data/figure_source_data/FigureS1_spatial_patterns.csv"
OUT = REPO / "results/figures/Figure2_spatial_patterns"
WORLD = Path(os.environ["NATURAL_EARTH_SHP"])
CRS = "+proj=aeqd +lat_0=90 +lon_0=0 +datum=WGS84 +units=m +no_defs"
WIDTH_MM, HEIGHT_MM, FONT_OFFSET = 180.0, 154.0, 2.0


def boundary_radius() -> float:
    transformer = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    _, y = transformer.transform(0, 20)
    return abs(y)


def draw_graticules(ax, transformer: Transformer) -> None:
    for latitude in [20, 40, 60, 80]:
        longitude = np.linspace(-179.5, 179.5, 721)
        x, y = transformer.transform(longitude, np.full_like(longitude, latitude))
        ax.plot(x, y, color="#B5B5B5", lw=.42, ls=(0, (3, 3)), zorder=.5)
    for longitude in [-120, -60, 0, 60, 120, 180]:
        latitude = np.linspace(20, 89.8, 281)
        x, y = transformer.transform(np.full_like(latitude, longitude), latitude)
        ax.plot(x, y, color="#BDBDBD", lw=.38, ls=(0, (3, 3)), zorder=.5)
    for longitude, label in [(-120, "120°W"), (0, "0°"),
                             (120, "120°E"), (180, "180°")]:
        x, y = transformer.transform(longitude, 17.7)
        ax.text(x, y, label, ha="center", va="center", fontsize=6.3,
                color="#555555", clip_on=False, zorder=7)
    for latitude in [20, 40, 60, 80]:
        x, y = transformer.transform(100, latitude)
        ax.text(x, y, f"{latitude}°N", ha="left", va="bottom", fontsize=6.2,
                color="#555555", bbox=dict(facecolor="white", edgecolor="none",
                alpha=.70, pad=.35), zorder=7)


def add_frequency_inset(ax_map, frame, color) -> None:
    ax = ax_map.inset_axes([-.055, .015, .40, .28], facecolor="white", zorder=9)
    bins = [-1e-12, .2, .4, .6, 1.0]
    labels = ["0–0.2", "0.2–0.4", "0.4–0.6", ">0.6"]
    groups = pd.cut(frame.event_frequency, bins=bins, labels=labels, include_lowest=True)
    values = groups.value_counts(sort=False, normalize=True).mul(100).reindex(labels).fillna(0)
    x = np.arange(len(labels))
    ax.bar(x, values, width=.72, color=color, edgecolor="none", zorder=2)
    for xx, value in zip(x, values):
        ax.text(xx, value + 1.0, f"{value:.1f}", ha="center", va="bottom", fontsize=5.4)
    ax.set(xticks=x, xticklabels=labels, ylabel="Frequency (%)",
           ylim=(0, max(58, values.max() + 8)))
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    ax.set_title("Frequency distribution", fontsize=7.0, pad=1.5)
    ax.grid(axis="y", color=GRID, lw=.32, zorder=0)
    ax.tick_params(labelsize=5.5, length=2)
    ax.yaxis.label.set_size(5.8)


def add_direction_inset(ax_map, frame) -> None:
    ax = ax_map.inset_axes([-.055, .015, .40, .28], facecolor="white", zorder=9)
    values = frame.loc[frame.mean_event_anomaly.notna(), "mean_event_anomaly"]
    nonzero = values.ne(0)
    values = values[nonzero]
    shares = np.array([(values < 0).mean(), (values > 0).mean()]) * 100
    x = np.arange(2)
    ax.bar(x, shares, width=.62, color=[UA, PA], edgecolor="none", zorder=2)
    for xx, value in zip(x, shares):
        ax.text(xx, value + 1.3, f"{value:.1f}", ha="center", va="bottom", fontsize=5.8)
    ax.set(xticks=x, xticklabels=["Earlier", "Later"], ylabel="Grids (%)", ylim=(0, 82))
    ax.set_title("Direction of shift", fontsize=7.0, pad=1.5)
    ax.grid(axis="y", color=GRID, lw=.32, zorder=0)
    ax.tick_params(labelsize=5.8, length=2)
    ax.yaxis.label.set_size(5.8)


def add_panel_label(ax, label) -> None:
    """Place every panel letter at the same unclipped axes-relative position."""
    ax.text(-.025, 1.015, label, transform=ax.transAxes,
            ha="left", va="bottom", fontsize=11 + FONT_OFFSET,
            fontweight="bold", color=CONTRAST, clip_on=False)


def draw_map(ax, world, frame, value, title, cmap, norm):
    world.plot(ax=ax, color="#F2F2F0", edgecolor="#A0A0A0", linewidth=.28, zorder=0)
    transformer = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
    draw_graticules(ax, transformer)
    points = gpd.GeoDataFrame(
        frame.copy(), geometry=gpd.points_from_xy(frame.longitude, frame.latitude), crs="EPSG:4326"
    ).to_crs(CRS)
    valid = points[value].notna()
    if (~valid).any():
        points.loc[~valid].plot(ax=ax, color="#D7D7D7", markersize=2.0, alpha=.65, zorder=1)
    points.loc[valid].plot(
        ax=ax, column=value, cmap=cmap, norm=norm, markersize=3.0,
        linewidth=0, alpha=.88, rasterized=True, zorder=2,
    )
    radius = boundary_radius()
    circle = plt.Circle((0, 0), radius, transform=ax.transData, fill=False,
                        edgecolor=CONTRAST, linewidth=.65, zorder=5)
    ax.add_patch(circle)
    for artist in ax.collections:
        artist.set_clip_path(circle)
    ax.set(xlim=(-radius, radius), ylim=(-radius, radius), aspect="equal", title=title)
    ax.set_axis_off()
    return ScalarMappable(norm=norm, cmap=cmap)


def save(fig):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".svg"), facecolor="white")
    fig.savefig(OUT.with_suffix(".pdf"), facecolor="white")
    fig.savefig(OUT.with_suffix(".png"), dpi=300, facecolor="white")
    fig.savefig(OUT.with_suffix(".tiff"), dpi=600, facecolor="white",
                pil_kwargs={"compression": "tiff_lzw"})


def main():
    set_style(FONT_OFFSET)
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "svg.fonttype": "none", "pdf.fonttype": 42,
    })
    data = pd.read_csv(DATA)
    world_geo = gpd.read_file(WORLD).to_crs("EPSG:4326")
    world_geo["geometry"] = world_geo.geometry.intersection(box(-180, 20, 180, 90))
    world = world_geo[~world_geo.geometry.is_empty].to_crs(CRS)
    fig, axes = plt.subplots(2, 2, figsize=(mm(WIDTH_MM), mm(HEIGHT_MM)))
    fig.subplots_adjust(left=.045, right=.855, bottom=.085, top=.94, wspace=.12, hspace=.25)

    freq_cmap = LinearSegmentedColormap.from_list("frequency", ["#EEF3F7", "#F3B47A", "#B33A3A"])
    # Negative anomalies denote earlier phenology (magenta); positive anomalies
    # denote later phenology (blue), matching the inset bars and colorbar labels.
    shift_cmap = LinearSegmentedColormap.from_list("shift", [UA, "#F7F7F5", PA])
    freq_norm = Normalize(0, .7)
    shift_norm = TwoSlopeNorm(vmin=-30, vcenter=0, vmax=30)
    frequency_sm = anomaly_sm = None
    for col, pheno in enumerate(["SOS", "EOS"]):
        q = data[data.pheno_type.eq(pheno)]
        frequency_sm = draw_map(axes[0, col], world, q, "event_frequency",
                                f"Pre-{pheno} event frequency", freq_cmap, freq_norm)
        anomaly_sm = draw_map(axes[1, col], world, q, "mean_event_anomaly",
                              f"Mean {pheno} anomaly in event years", shift_cmap, shift_norm)
        add_frequency_inset(axes[0, col], q, "#D97B55")
        add_direction_inset(axes[1, col], q)
        add_panel_label(axes[0, col], "ab"[col])
        add_panel_label(axes[1, col], "cd"[col])

    cax1 = fig.add_axes([.88, .575, .014, .30])
    cb1 = fig.colorbar(frequency_sm, cax=cax1, orientation="vertical")
    cb1.set_label("Event frequency", rotation=270, labelpad=14)
    cax2 = fig.add_axes([.88, .125, .014, .30])
    cb2 = fig.colorbar(anomaly_sm, cax=cax2, orientation="vertical")
    cb2.ax.yaxis.set_ticks_position("left")
    cax2.text(1.55, .02, "← Earlier", transform=cax2.transAxes,
              ha="left", va="bottom", fontsize=7.2 + FONT_OFFSET,
              fontweight="bold", color=UA, clip_on=False)
    cax2.text(1.55, .98, "→ Later", transform=cax2.transAxes,
              ha="left", va="top", fontsize=7.2 + FONT_OFFSET,
              fontweight="bold", color=PA, clip_on=False)
    save(fig)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()


