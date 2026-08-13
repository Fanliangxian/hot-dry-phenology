from __future__ import annotations

import json
from pathlib import Path
import os

import numpy as np
import pandas as pd
import rasterio

PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
INV = PROJECT / "stage2_covariate_inventory" / "results"
ROOT = PROJECT / "stage2_covariate_inventory" / "stage2b_results"
ASSETS = ROOT / "assets"


def sample_raster(path: Path, coordinates: list[tuple[float, float]]) -> np.ndarray:
    with rasterio.open(path) as src:
        if src.crs is None or src.crs.to_epsg() != 4326:
            raise ValueError(f"Expected EPSG:4326 raster: {path}; found {src.crs}")
        values = np.array([v[0] for v in src.sample(coordinates)], dtype=float)
        if src.nodata is not None:
            values[np.isclose(values, src.nodata)] = np.nan
        return values


def standardized_mean_difference(frame: pd.DataFrame, variable: str, weight: str) -> float:
    groups = []
    for label in ["PA", "UA"]:
        part = frame[frame.landscape_type == label]
        x, w = part[variable].to_numpy(float), part[weight].to_numpy(float)
        ok = np.isfinite(x) & np.isfinite(w) & (w > 0)
        x, w = x[ok], w[ok]
        mean = np.average(x, weights=w)
        var = np.average((x - mean) ** 2, weights=w)
        groups.append((mean, var))
    pooled = np.sqrt((groups[0][1] + groups[1][1]) / 2)
    return (groups[0][0] - groups[1][0]) / pooled if pooled > 0 else np.nan


def main() -> None:
    pixels = pd.read_parquet(INV / "pixel_static_covariate_lookup.parquet")
    pixels["sin_lon"] = np.sin(np.deg2rad(pixels.longitude))
    pixels["cos_lon"] = np.cos(np.deg2rad(pixels.longitude))
    cells = pixels.groupby(["era_cell_id", "landscape_type"], observed=True).agg(
        spatial_pixel_count=("pixel_row", "size"),
        latitude=("latitude", "mean"), longitude=("longitude", "mean"),
        veg_frac_mean=("veg_frac_pct", "mean"),
        sin_lon=("sin_lon", "mean"), cos_lon=("cos_lon", "mean"),
    ).reset_index()
    climate = pd.read_parquet(INV / "era5_background_covariates.parquet")
    cells = cells.merge(climate, on="era_cell_id", how="left", validate="many_to_one")
    coords = list(zip(cells.longitude, cells.latitude))

    precip_files = sorted((ASSETS / "worldclim21_prec_10m").glob("*prec_*.tif"))
    if len(precip_files) != 12:
        raise RuntimeError(f"Expected 12 monthly precipitation rasters, found {len(precip_files)}")
    monthly = np.column_stack([sample_raster(path, coords) for path in precip_files])
    cells["precip_annual_mm"] = np.nansum(monthly, axis=1)
    cells["precip_warm_apr_sep_mm"] = np.nansum(monthly[:, 3:9], axis=1)
    month_mean = np.nanmean(monthly, axis=1)
    cells["precip_seasonality_cv"] = np.nanstd(monthly, axis=1) / np.where(month_mean > 0, month_mean, np.nan)
    elev_file = next((ASSETS / "worldclim21_elev_10m").glob("*.tif"))
    cells["elevation_m"] = sample_raster(elev_file, coords)

    cells["landcover_status"] = "unavailable_current_grid"
    cells["landcover_source"] = "MCD12Q1.061 LC_Type1 planned; incompatible legacy 0.25-degree table not joined"
    cells["lat_band_10deg"] = pd.cut(cells.latitude, np.arange(20, 70, 10), right=False).astype(str)
    cells.to_parquet(ROOT / "stage2b_cell_landscape_covariates.parquet", index=False)

    variables = ["precip_annual_mm", "precip_warm_apr_sep_mm", "precip_seasonality_cv", "elevation_m"]
    coverage = []
    scoped = cells[cells.latitude.between(20, 60, inclusive="left")].copy()
    for band, part in scoped.groupby("lat_band_10deg", observed=True):
        for variable in variables:
            coverage.append({
                "latitude_band": str(band), "variable": variable, "n_units": len(part),
                "missing_n": int(part[variable].isna().sum()),
                "missing_fraction": float(part[variable].isna().mean()),
                "smd_PA_minus_UA_pixel_weighted": standardized_mean_difference(part, variable, "spatial_pixel_count"),
            })
    pd.DataFrame(coverage).to_csv(ROOT / "stage2b_covariate_coverage.csv", index=False, encoding="utf-8-sig")
    qc = {
        "n_cell_landscape_units": len(cells),
        "n_units_20_60N": len(scoped),
        "precip_rasters": [p.name for p in precip_files],
        "elevation_raster": elev_file.name,
        "landcover_current_grid_available": False,
        "join_key": ["era_cell_id", "landscape_type"],
    }
    (ROOT / "stage2b_covariate_build_qc.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()


