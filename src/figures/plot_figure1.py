from __future__ import annotations

from pathlib import Path
import os
import sys

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import box

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from figure_style import GRID, PA, mm, set_style

REPO = HERE.parents[1]
D2 = REPO
DATA = D2 / "data/figure_source_data"
OUT = D2 / "results/figures/Figure1_study_domain"
WORLD = Path(os.environ["NATURAL_EARTH_SHP"])
WIDTH_MM, HEIGHT_MM, FONT_OFFSET = 180.0, 124.0, 2.0
UA_LIGHT = "#D56F9E"
TARGET_CRS = "+proj=aeqd +lat_0=90 +lon_0=0 +datum=WGS84 +units=m +no_defs"


def draw_graticules(ax, transformer: Transformer) -> None:
    for latitude in [20, 40, 60, 80]:
        longitude = np.linspace(-179.5, 179.5, 721)
        x, y = transformer.transform(longitude, np.full_like(longitude, latitude))
        ax.plot(x, y, color="#AFAFAF", lw=0.55, ls=(0, (3, 3)), zorder=1)
    for longitude in [-120, -60, 0, 60, 120, 180]:
        latitude = np.linspace(20, 89.8, 281)
        x, y = transformer.transform(np.full_like(latitude, longitude), latitude)
        ax.plot(x, y, color="#B8B8B8", lw=0.5, ls=(0, (3, 3)), zorder=1)

    for longitude, label in [(-120, "120°W"), (-60, "60°W"), (0, "0°"),
                             (60, "60°E"), (120, "120°E"), (180, "180°")]:
        x, y = transformer.transform(longitude, 17.5)
        ax.text(x, y, label, ha="center", va="center", fontsize=7.2, color="#555555", clip_on=False)
    for latitude in [20, 40, 60, 80]:
        x, y = transformer.transform(20, latitude)
        ax.text(x, y, f"{latitude}°N", ha="left", va="bottom", fontsize=7.0, color="#555555",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.70, pad=0.5), zorder=7)


def add_count_inset(ax_map, counts: pd.DataFrame) -> None:
    ax = ax_map.inset_axes([-0.055, 0.005, 0.34, 0.30], facecolor=(1, 1, 1, 0.95), zorder=8)
    units = ["source pixels", "common-support cell鈥搇andscape units"]
    x = np.arange(2)
    width = 0.34
    for landscape, color, offset in [("PA", PA, -width/2), ("UA", UA_LIGHT, width/2)]:
        q = counts[counts.landscape_type.eq(landscape)].set_index("unit").reindex(units)
        values = q["count"].to_numpy()
        ax.bar(x + offset, values / 1000, width=width, color=color, label=landscape, zorder=2)
        for xx, value in zip(x + offset, values):
            ax.text(xx, value/1000 + 2.0, f"{value:,}", ha="center", va="bottom", fontsize=6.5, zorder=3)
    ax.set(xticks=x, xticklabels=["Pixels", "Units"], ylim=(0, 112), ylabel="Count (thousands)")
    ax.grid(axis="y", color=GRID, lw=0.4, zorder=0)
    ax.legend(ncol=2, loc="upper right", fontsize=7.0, handlelength=1.4, columnspacing=0.7)
    ax.tick_params(labelsize=7.2)
    ax.yaxis.label.set_size(7.5)
    ax.set_title("Sample composition", fontsize=9.0, pad=2.5)


def save(fig) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT.with_suffix(".svg"), facecolor="white")
    fig.savefig(OUT.with_suffix(".pdf"), facecolor="white")
    fig.savefig(OUT.with_suffix(".png"), dpi=300, facecolor="white")
    fig.savefig(OUT.with_suffix(".tiff"), dpi=600, facecolor="white", pil_kwargs={"compression": "tiff_lzw"})


def main() -> None:
    set_style(FONT_OFFSET)
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    })
    points = pd.read_csv(DATA / "Figure1a.csv")
    counts = pd.read_csv(DATA / "Figure1b.csv")
    world_geo = gpd.read_file(WORLD).to_crs("EPSG:4326")
    world_geo["geometry"] = world_geo.geometry.intersection(box(-180, 20, 180, 90))
    world = world_geo[~world_geo.geometry.is_empty].to_crs(TARGET_CRS)
    transformer = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    px, py = transformer.transform(points.longitude.to_numpy(), points.latitude.to_numpy())
    points = points.assign(map_x=px, map_y=py)

    fig = plt.figure(figsize=(mm(WIDTH_MM), mm(HEIGHT_MM)))
    ax = fig.add_axes([0.17, 0.065, 0.78, 0.80])
    world.plot(ax=ax, color="#F1F1EF", edgecolor="#A9A9A9", linewidth=0.35, zorder=0)
    draw_graticules(ax, transformer)
    for landscape, color, size, alpha, zorder in [
        ("PA", PA, 0.75, 0.30, 2),
        ("UA", UA_LIGHT, 0.85, 0.24, 3),
    ]:
        q = points[points.landscape_type.eq(landscape)]
        ax.scatter(q.map_x, q.map_y, s=size, c=color, alpha=alpha, linewidths=0,
                   rasterized=True, zorder=zorder)

    _, boundary_y = transformer.transform(0, 20)
    radius = abs(boundary_y)
    ax.set_xlim(-radius * 1.06, radius * 1.06)
    ax.set_ylim(-radius * 1.06, radius * 1.06)
    ax.set_aspect("equal", adjustable="box")
    outer = plt.Circle((0, 0), radius, fill=False, edgecolor="#333333", linewidth=0.9, zorder=6)
    ax.add_patch(outer)
    ax.set_axis_off()
    add_count_inset(ax, counts)
    ax.set_title("Study domain and analytical samples", fontsize=11.0, fontweight="bold", pad=4)
    save(fig)
    plt.close(fig)
    print(OUT)


if __name__ == "__main__":
    main()

