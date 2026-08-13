from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path
import os

import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from scipy.stats import norm


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage6_baseline_repair_audit" / "full_propagation"
INPUT = ROOT / "model_input" / "occurrence"
OUT = ROOT / "results" / "occurrence"
STRATEGIES = ["unadjusted", "covariate_adjusted", "overlap_weighted_adjusted"]
LATITUDES = [25.0, 35.0, 45.0, 55.0]
REPLICATES = 999
SEED = 20260807


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


OCC = load_module(
    "full_occurrence_base",
    PROJECT / "stage2_covariate_inventory" / "stage2b_landcover" / "scripts"
    / "run_stage2b_landcover_models.py",
)


def load_partition(gap: int, duration: int, pheno: str) -> pd.DataFrame:
    dataset = ds.dataset(INPUT, format="parquet")
    filt = (
        (ds.field("gap_days") == gap) & (ds.field("event_min_days") == duration)
        & (ds.field("pheno_type") == pheno)
    )
    frame = dataset.to_table(filter=filt).to_pandas()
    if frame.empty:
        raise ValueError(f"Empty occurrence partition: {(gap, duration, pheno)}")
    frame["mean_anomaly_crossfit"] = frame.mean_anomaly_all_year_linear_loo
    frame["mean_abs_anomaly_crossfit"] = frame.mean_abs_anomaly_all_year_linear_loo
    return frame


def bh_adjust(values: pd.Series) -> pd.Series:
    p = values.to_numpy(float)
    order = np.argsort(p)
    ranked = p[order] * len(p) / (np.arange(len(p)) + 1)
    adjusted_ordered = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted = np.empty_like(adjusted_ordered)
    adjusted[order] = np.minimum(adjusted_ordered, 1.0)
    return pd.Series(adjusted, index=values.index)


def contrast_rows(result, meta: dict) -> list[dict]:
    covariance = np.asarray(result.cov_params())
    params = np.asarray(result.params)
    rows = []
    for latitude in np.arange(24.0, 59.01, 0.25):
        vectors = {}
        for landscape in ["PA", "UA"]:
            vector = OCC.design_row(result, latitude, landscape, 1) - OCC.design_row(
                result, latitude, landscape, 0
            )
            vectors[landscape] = vector
            estimate = float(vector @ params)
            se = math.sqrt(max(float(vector @ covariance @ vector), 0.0))
            rows.append({
                **meta, "latitude": latitude, "contrast": f"event_effect_{landscape}",
                "estimate": estimate, "std_error": se,
                "conf_low": estimate - 1.959963984540054 * se,
                "conf_high": estimate + 1.959963984540054 * se,
                "p_value": float(2 * norm.sf(abs(estimate / se))) if se > 0 else np.nan,
            })
        vector = vectors["UA"] - vectors["PA"]
        estimate = float(vector @ params)
        se = math.sqrt(max(float(vector @ covariance @ vector), 0.0))
        rows.append({
            **meta, "latitude": latitude, "contrast": "UA_minus_PA_event_effect",
            "estimate": estimate, "std_error": se,
            "conf_low": estimate - 1.959963984540054 * se,
            "conf_high": estimate + 1.959963984540054 * se,
            "p_value": float(2 * norm.sf(abs(estimate / se))) if se > 0 else np.nan,
        })
    return rows


def spatial_rows(result, used: pd.DataFrame, weights: pd.Series, meta: dict,
                 rng: np.random.Generator) -> list[dict]:
    x = np.asarray(result.model.exog, float)
    residual = np.asarray(result.resid, float)
    w = weights.to_numpy(float)
    bread = np.linalg.pinv(x.T @ (w[:, None] * x))
    longitude = np.rad2deg(np.arctan2(used.sin_lon.to_numpy(float), used.cos_lon.to_numpy(float)))
    beta = np.asarray(result.params)
    rows = []
    for block_degrees in [5, 10]:
        blocks = (
            np.floor((used.latitude.to_numpy(float) - 20) / block_degrees).astype(int).astype(str)
            + "_" + np.floor((longitude + 180) / block_degrees).astype(int).astype(str)
        )
        scores = (
            pd.DataFrame(x * (w * residual)[:, None]).assign(block=blocks)
            .groupby("block", sort=False).sum().to_numpy()
        )
        multipliers = rng.choice([-1.0, 1.0], size=(REPLICATES, scores.shape[0]))
        draws = beta[None, :] + (multipliers @ scores) @ bread.T
        for latitude in LATITUDES:
            ua = OCC.design_row(result, latitude, "UA", 1) - OCC.design_row(result, latitude, "UA", 0)
            pa = OCC.design_row(result, latitude, "PA", 1) - OCC.design_row(result, latitude, "PA", 0)
            vector = ua - pa
            values = draws @ vector
            estimate = float(beta @ vector)
            rows.append({
                **meta, "latitude": latitude, "contrast": "UA_minus_PA_event_effect",
                "block_degrees": block_degrees, "n_blocks": scores.shape[0],
                "replicates": REPLICATES, "estimate": estimate,
                "bootstrap_se": float(values.std(ddof=1)),
                "conf_low": float(np.quantile(values, 0.025)),
                "conf_high": float(np.quantile(values, 0.975)),
                "sign_stability": float(np.mean(np.sign(values) == np.sign(estimate))),
            })
    return rows


def apply_families(tests: pd.DataFrame) -> pd.DataFrame:
    tests["p_value_bh"] = np.nan
    tests["bh_family"] = "exploratory_window_by_adjustment_cross"
    primary = (
        tests.gap_days.eq(0) & tests.event_min_days.eq(3)
        & tests.strategy.eq("overlap_weighted_adjusted")
    )
    window = tests.strategy.eq("overlap_weighted_adjusted") & ~primary
    adjustment = (
        tests.gap_days.eq(0) & tests.event_min_days.eq(3)
        & tests.strategy.isin(["unadjusted", "covariate_adjusted"])
    )
    for mask, label, expected in [
        (primary, "primary_final_strategy_2", 2),
        (window, "window_sensitivity_final_strategy_10", 10),
        (adjustment, "adjustment_sensitivity_primary_window_4", 4),
    ]:
        if int(mask.sum()) != expected:
            raise ValueError(f"BH family {label} has {int(mask.sum())}, expected {expected}")
        tests.loc[mask, "p_value_bh"] = bh_adjust(tests.loc[mask, "p_value"])
        tests.loc[mask, "bh_family"] = label
    return tests


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    curves, tests, models, spatial, failures = [], [], [], [], []
    rng = np.random.default_rng(SEED)
    for gap in [0, 8, 16]:
        for duration in [3, 5]:
            for pheno in ["SOS", "EOS"]:
                data = load_partition(gap, duration, pheno)
                for strategy in STRATEGIES:
                    meta = {
                        "spec_version": "baseline-full-propagation-v1.0",
                        "baseline": "all_year_linear_loo", "gap_days": gap,
                        "event_min_days": duration, "pheno_type": pheno, "strategy": strategy,
                    }
                    try:
                        result, used, formula, weights = OCC.fit_model(data, strategy)
                        curves.extend(contrast_rows(result, meta))
                        tests.append(OCC.base.global_triple_test(result, meta))
                        residual = np.asarray(result.resid, float)
                        models.append({
                            **meta, "n_units": int(result.nobs),
                            "n_era_cells": int(used.era_cell_id.nunique()),
                            "analysis_weight_sum": float(weights.sum()),
                            "weighted_residual_mean": float(np.average(residual, weights=weights)),
                            "weighted_residual_rmse": float(np.sqrt(np.average(residual ** 2, weights=weights))),
                            "formula": formula,
                        })
                        if strategy == "overlap_weighted_adjusted":
                            spatial.extend(spatial_rows(result, used, weights, meta, rng))
                        print(json.dumps({**meta, "n": int(result.nobs)}), flush=True)
                    except Exception as exc:
                        failures.append({**meta, "error": repr(exc)})
                        print(json.dumps({**meta, "FAILED": repr(exc)}), flush=True)
    tests_frame = apply_families(pd.DataFrame(tests))
    pd.DataFrame(curves).to_csv(OUT / "occurrence_effect_curves.csv", index=False, encoding="utf-8-sig")
    tests_frame.to_csv(OUT / "occurrence_global_tests.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(models).to_csv(OUT / "occurrence_model_summary.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(spatial).to_csv(OUT / "occurrence_spatial_bootstrap.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(failures).to_csv(OUT / "occurrence_model_failures.csv", index=False, encoding="utf-8-sig")
    status = {
        "models_expected": 36, "models_fit": len(models), "failures": len(failures),
        "global_tests": len(tests_frame), "curve_rows": len(curves),
        "spatial_rows_expected": 96, "spatial_rows": len(spatial),
        "replicates": REPLICATES,
    }
    status["all_checks_pass"] = (
        len(models) == 36 and not failures and len(tests_frame) == 36 and len(spatial) == 96
    )
    (OUT / "occurrence_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if status["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


