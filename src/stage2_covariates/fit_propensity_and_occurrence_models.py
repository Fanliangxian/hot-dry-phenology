from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import os

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import statsmodels.api as sm
import statsmodels.formula.api as smf
from patsy import build_design_matrices

PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage2_covariate_inventory" / "stage2b_landcover"
OUT = ROOT / "results"
OUT.mkdir(parents=True, exist_ok=True)
BASE_SCRIPT = PROJECT / "stage2_covariate_inventory" / "scripts" / "run_stage2a_overlap_adjusted_models.py"
STAGE2B_CELLS = PROJECT / "stage2_covariate_inventory" / "stage2b_results" / "stage2b_cell_landscape_covariates.parquet"
LANDCOVER = ROOT / "stage2b_landcover_cell_landscape.parquet"
INPUT = PROJECT / "stage1_window_baseline" / "results" / "fixed_window_runs" / "fixed_window_v01" / "continuous_latitude_models" / "continuous_latitude_model_input.parquet"

spec = importlib.util.spec_from_file_location("stage2a_base_lc", BASE_SCRIPT)
base = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(base)
base.OUT = OUT
base.INPUT = INPUT

# Fractions sum to one. Grassland is the reference because lc_other_frac is structurally zero.
LC_COVARS = [
    "lc_forest_frac", "lc_shrubland_frac", "lc_savanna_frac", "lc_wetland_frac",
    "lc_cropland_frac", "lc_urban_frac", "lc_snow_frac", "lc_barren_frac", "lc_water_frac",
]
BASE_COVARS = [
    "latitude", "veg_frac_mean", "tmax_mean", "tmax_sd", "vpd_mean", "vpd_sd",
    "log_precip_annual_z", "precip_seasonality_z", "elevation_z", "sin_lon", "cos_lon",
]
base.COVARS = BASE_COVARS + LC_COVARS


def build_cell_landscape() -> pd.DataFrame:
    cells = pd.read_parquet(STAGE2B_CELLS)
    lc = pd.read_parquet(LANDCOVER)
    cells = cells.merge(lc, on=["era_cell_id", "landscape_type"], how="inner", validate="one_to_one")
    cells = cells[cells.latitude.between(20, 60, inclusive="left") & (cells.climate_valid_fraction > 0)].copy()
    cells["log_precip_annual"] = np.log1p(cells.precip_annual_mm)
    standardized = {
        "tmax_mean": "tmax_mean_z", "tmax_sd": "tmax_sd_z", "vpd_mean": "vpd_mean_z", "vpd_sd": "vpd_sd_z",
        "log_precip_annual": "log_precip_annual_z", "precip_seasonality_cv": "precip_seasonality_z",
        "elevation_m": "elevation_z",
    }
    for variable, output in standardized.items():
        cells[output] = (cells[variable] - cells[variable].mean()) / cells[variable].std()
    required = ["precip_seasonality_z", "elevation_z", "log_precip_annual_z"] + LC_COVARS
    cells = cells.dropna(subset=required)
    cells["is_UA"] = (cells.landscape_type == "UA").astype(int)
    cells["lat_stratum_5deg"] = pd.cut(cells.latitude, np.arange(20, 65, 5), right=False, include_lowest=True)
    lc_terms = " + ".join(LC_COVARS)
    formula = (
        "is_UA ~ latitude + cr(veg_frac_mean, df=3, constraints='center') + "
        "tmax_mean_z + tmax_sd_z + vpd_mean_z + vpd_sd_z + "
        "cr(log_precip_annual_z, df=3, constraints='center') + precip_seasonality_z + "
        "cr(elevation_z, df=3, constraints='center') + sin_lon + cos_lon + " + lc_terms
    )
    parts, models = [], []
    for stratum, group in cells.groupby("lat_stratum_5deg", observed=True):
        fit = smf.glm(formula, group, family=sm.families.Binomial(), freq_weights=group.spatial_pixel_count).fit(maxiter=300)
        part = group.copy()
        part["propensity_UA"] = np.clip(fit.predict(group), 1e-8, 1 - 1e-8)
        parts.append(part)
        models.append({"lat_stratum_5deg": str(stratum), "n_units": len(group),
                       "converged": bool(fit.converged), "aic": float(fit.aic)})
    cells = pd.concat(parts, ignore_index=True)
    cells["overlap_weight"] = np.where(cells.is_UA == 1, 1 - cells.propensity_UA, cells.propensity_UA)
    cells["target_weight"] = cells.spatial_pixel_count * cells.overlap_weight
    cells["lat_stratum_5deg"] = cells.lat_stratum_5deg.astype(str)
    cells.to_parquet(OUT / "stage2b_landcover_cell_landscape_propensity_weights.parquet", index=False)
    base.smd_table(cells).to_csv(OUT / "stage2b_landcover_overlap_balance_smd.csv", index=False, encoding="utf-8-sig")
    (OUT / "stage2b_landcover_propensity_model.json").write_text(
        json.dumps({"formula": formula, "composition_reference": "Grassland", "models": models}, indent=2), encoding="utf-8")
    return cells


def prepare_outcome_input(cells: pd.DataFrame) -> Path:
    target = OUT / "stage2b_landcover_model_input.parquet"
    cols = [
        "era_cell_id", "landscape_type", "veg_frac_mean", "sin_lon", "cos_lon", "tmax_mean_z", "tmax_sd_z",
        "vpd_mean_z", "vpd_sd_z", "log_precip_annual_z", "precip_seasonality_z", "elevation_z",
        "propensity_UA", "overlap_weight",
    ] + LC_COVARS
    lookup = cells[cols]
    parts = []
    for batch in pq.ParquetFile(INPUT).iter_batches(batch_size=500_000):
        frame = batch.to_pandas()
        frame = frame[frame.latitude.between(20, 60, inclusive="left")]
        parts.append(frame.merge(lookup, on=["era_cell_id", "landscape_type"], how="inner", validate="many_to_one"))
    pd.concat(parts, ignore_index=True).to_parquet(target, index=False)
    return target


def fit_model(data: pd.DataFrame, strategy: str):
    work = data.dropna(subset=["mean_anomaly_crossfit", "era_cell_id", "n_pixels"]).copy()
    work["landscape_type"] = pd.Categorical(work.landscape_type, categories=["PA", "UA"])
    work["year_c"] = work.year - work.year.mean()
    base_formula = "mean_anomaly_crossfit ~ cr(latitude, df=4, constraints='center') * event * C(landscape_type) + year_c"
    adjustment = (
        " + cr(veg_frac_mean, df=3, constraints='center') + tmax_mean_z + tmax_sd_z + vpd_mean_z + vpd_sd_z"
        " + cr(log_precip_annual_z, df=3, constraints='center') + precip_seasonality_z"
        " + cr(elevation_z, df=3, constraints='center') + sin_lon + cos_lon + " + " + ".join(LC_COVARS)
    )
    formula = base_formula if strategy == "unadjusted" else base_formula + adjustment
    weights = work.n_pixels if strategy != "overlap_weighted_adjusted" else work.n_pixels * work.overlap_weight
    model = smf.wls(formula, work, weights=weights)
    used = model.data.row_labels
    result = model.fit(cov_type="cluster", cov_kwds={"groups": work.loc[used, "era_cell_id"].to_numpy()})
    return result, work.loc[used], formula, weights.loc[used]


def design_row(result, latitude, landscape, event):
    values = {
        "latitude": [latitude], "landscape_type": [landscape], "event": [event], "year_c": [0.0],
        "veg_frac_mean": [80.0], "tmax_mean_z": [0.0], "tmax_sd_z": [0.0], "vpd_mean_z": [0.0],
        "vpd_sd_z": [0.0], "log_precip_annual_z": [0.0], "precip_seasonality_z": [0.0],
        "elevation_z": [0.0], "sin_lon": [0.0], "cos_lon": [0.0],
    }
    values.update({column: [0.0] for column in LC_COVARS})
    frame = pd.DataFrame(values)
    frame["landscape_type"] = pd.Categorical(frame.landscape_type, categories=["PA", "UA"])
    return np.asarray(build_design_matrices([result.model.data.design_info], frame)[0])[0]


def rename_outputs() -> None:
    mapping = {
        "stage2a_effect_curves.csv": "stage2b_landcover_effect_curves.csv",
        "stage2a_model_summary.csv": "stage2b_landcover_model_summary.csv",
        "stage2a_global_triple_interaction_tests.csv": "stage2b_landcover_global_tests.csv",
        "stage2a_model_failures.csv": "stage2b_landcover_model_failures.csv",
        "run_status.json": "stage2b_landcover_run_status.json",
    }
    for old, new in mapping.items():
        source = OUT / old
        if source.exists():
            source.replace(OUT / new)


if __name__ == "__main__":
    base.build_cell_landscape = build_cell_landscape
    base.prepare_outcome_input = prepare_outcome_input
    base.fit_model = fit_model
    base.design_row = design_row
    code = base.main()
    rename_outputs()
    raise SystemExit(code)


