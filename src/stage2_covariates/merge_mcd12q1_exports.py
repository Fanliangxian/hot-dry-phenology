from __future__ import annotations

import json
from pathlib import Path
import os

import numpy as np
import pandas as pd

PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage2_covariate_inventory" / "stage2b_landcover"
DOWNLOAD = ROOT / "gee_download"
SOURCE = PROJECT / "stage2_covariate_inventory" / "results" / "pixel_static_covariate_lookup.parquet"

IGBP_TO_BROAD = {
    1: "Forest", 2: "Forest", 3: "Forest", 4: "Forest", 5: "Forest",
    6: "Shrubland", 7: "Shrubland", 8: "Savanna", 9: "Savanna",
    10: "Grassland", 11: "Wetland", 12: "Cropland", 13: "Urban",
    14: "Cropland", 15: "Snow", 16: "Barren", 17: "Water",
}
BROAD_CLASSES = ["Forest", "Shrubland", "Savanna", "Grassland", "Wetland", "Cropland",
                 "Urban", "Snow", "Barren", "Water", "Other"]


def aggregate_landcover(exports: pd.DataFrame, source: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    expected = source[source.latitude.between(20, 60, inclusive="left")].copy()
    expected["study_pixel_id"] = "R" + expected.pixel_row.astype(str) + "_C" + expected.pixel_col.astype(str)
    if exports.study_pixel_id.duplicated().any():
        raise ValueError("Duplicate study_pixel_id values in Earth Engine exports")
    exports = exports.copy()
    exports["igbp_mode"] = pd.to_numeric(exports.igbp_mode, errors="coerce")
    valid_class = exports.igbp_mode.between(1, 17, inclusive="both")
    exports.loc[~valid_class, "igbp_mode"] = np.nan
    joined = expected[["study_pixel_id", "era_cell_id", "landscape_type", "pixel_area_km2", "latitude"]].merge(
        exports[["study_pixel_id", "igbp_mode", "valid_years", "mode_persistence"]],
        on="study_pixel_id", how="left", validate="one_to_one"
    )
    joined["landcover_group"] = joined.igbp_mode.map(IGBP_TO_BROAD).fillna("Other")
    joined["valid_landcover"] = joined.igbp_mode.notna()
    valid = joined[joined.valid_landcover].copy()
    valid["weighted_persistence"] = valid.pixel_area_km2 * valid.mode_persistence
    totals = valid.groupby(["era_cell_id", "landscape_type"], observed=True).pixel_area_km2.sum().rename("valid_lc_area_km2")
    fractions = valid.pivot_table(index=["era_cell_id", "landscape_type"], columns="landcover_group",
                                  values="pixel_area_km2", aggfunc="sum", fill_value=0).reindex(columns=BROAD_CLASSES, fill_value=0)
    fractions = fractions.div(totals, axis=0).rename(columns=lambda x: f"lc_{x.lower()}_frac")
    persistence = valid.groupby(["era_cell_id", "landscape_type"], observed=True).agg(
        persistence_numerator=("weighted_persistence", "sum"), valid_pixel_count=("study_pixel_id", "size")
    )
    out = fractions.join(totals).join(persistence)
    out["lc_mode_persistence_mean"] = out.persistence_numerator / out.valid_lc_area_km2
    out = out.drop(columns="persistence_numerator").reset_index()
    frac_cols = [f"lc_{name.lower()}_frac" for name in BROAD_CLASSES]
    if not np.allclose(out[frac_cols].sum(axis=1), 1.0, atol=1e-10):
        raise AssertionError("Land-cover fractions do not sum to one")
    qc = {"expected_pixels": len(expected), "exported_unique_pixels": int(exports.study_pixel_id.nunique()),
          "matched_valid_pixels": int(joined.valid_landcover.sum()), "missing_or_invalid_pixels": int((~joined.valid_landcover).sum()),
          "coverage_fraction": float(joined.valid_landcover.mean()), "cell_landscape_units": len(out)}
    return out, qc


def main() -> None:
    paths = sorted(DOWNLOAD.glob("stage2b_mcd12q1_*.csv"))
    if len(paths) != 4:
        raise FileNotFoundError(f"Expected four Earth Engine CSV exports in {DOWNLOAD}; found {len(paths)}")
    exports = pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)
    source = pd.read_parquet(SOURCE)
    out, qc = aggregate_landcover(exports, source)
    out.to_parquet(ROOT / "stage2b_landcover_cell_landscape.parquet", index=False)
    summary = out.groupby("landscape_type").agg(
        n_cell_landscape=("era_cell_id", "size"), mean_mode_persistence=("lc_mode_persistence_mean", "mean")
    ).reset_index()
    summary.to_csv(ROOT / "stage2b_landcover_coverage.csv", index=False, encoding="utf-8-sig")
    (ROOT / "stage2b_landcover_qc.json").write_text(json.dumps(qc, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()


