from __future__ import annotations

import json
from pathlib import Path
import os

import pandas as pd
import pyarrow.dataset as ds


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage6_baseline_repair_audit" / "full_propagation"
OCC_SOURCE = ROOT / "model_input" / "occurrence"
DOSE_SOURCE = ROOT / "model_input" / "dose"
OUT = ROOT / "model_input" / "resistance"
CELL_LOOKUP = (
    PROJECT / "stage2_covariate_inventory" / "stage2b_landcover" / "results"
    / "stage2b_landcover_cell_landscape_propensity_weights.parquet"
)


def raw_lookup() -> pd.DataFrame:
    frame = pd.read_parquet(
        CELL_LOOKUP, columns=["era_cell_id", "landscape_type", "precip_annual_mm", "vpd_mean"]
    )
    if frame.duplicated(["era_cell_id", "landscape_type"]).any():
        raise ValueError("Raw moderator lookup is not one-to-one")
    return frame


def write(frame: pd.DataFrame, estimand: str, pheno: str) -> dict:
    target = OUT / f"estimand={estimand}" / f"pheno_type={pheno}"
    target.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(target / "part.parquet", index=False)
    return {
        "estimand": estimand, "pheno_type": pheno, "rows": len(frame),
        "era_cells": int(frame.era_cell_id.nunique()),
        "missing_outcomes": int(frame[["mean_anomaly_crossfit", "mean_abs_anomaly_crossfit"]].isna().sum().sum()),
        "missing_primary_moderators": int(frame[["precip_annual_mm", "lc_forest_frac"]].isna().sum().sum()),
        "invalid_weights": int((frame.analysis_weight <= 0).sum()),
    }


def main() -> int:
    if any(OUT.rglob("*.parquet")):
        raise FileExistsError(f"Resistance inputs already exist: {OUT}")
    lookup = raw_lookup()
    rows = []
    occurrence = ds.dataset(OCC_SOURCE, format="parquet")
    dose = ds.dataset(DOSE_SOURCE, format="parquet")
    for pheno in ["SOS", "EOS"]:
        occ_filter = (
            (ds.field("gap_days") == 0) & (ds.field("event_min_days") == 3)
            & (ds.field("pheno_type") == pheno)
        )
        frame = occurrence.to_table(filter=occ_filter).to_pandas()
        frame["mean_anomaly_crossfit"] = frame.mean_anomaly_all_year_linear_loo
        frame["mean_abs_anomaly_crossfit"] = frame.mean_abs_anomaly_all_year_linear_loo
        frame = frame.merge(lookup, on=["era_cell_id", "landscape_type"], how="left", validate="many_to_one")
        frame["analysis_weight"] = frame.n_pixels * frame.overlap_weight
        frame["year_c"] = frame.year - frame.year.mean()
        rows.append(write(frame, "occurrence", pheno))

        dose_filter = (
            (ds.field("gap_days") == 0) & (ds.field("event_min_days") == 3)
            & (ds.field("dose_metric") == "cumulative_days")
            & (ds.field("pheno_type") == pheno)
        )
        frame = dose.to_table(filter=dose_filter).to_pandas()
        frame["mean_anomaly_crossfit"] = frame.mean_anomaly_all_year_linear_loo
        frame["mean_abs_anomaly_crossfit"] = frame.mean_abs_anomaly_all_year_linear_loo
        frame = frame.merge(lookup, on=["era_cell_id", "landscape_type"], how="left", validate="many_to_one")
        rows.append(write(frame, "dose", pheno))

    audit = pd.DataFrame(rows)
    audit.to_csv(OUT / "resistance_input_qc.csv", index=False, encoding="utf-8-sig")
    status = {
        "partitions": len(audit), "rows": int(audit.rows.sum()),
        "missing_outcomes": int(audit.missing_outcomes.sum()),
        "missing_primary_moderators": int(audit.missing_primary_moderators.sum()),
        "invalid_weights": int(audit.invalid_weights.sum()),
    }
    status["all_checks_pass"] = (
        status["partitions"] == 4
        and status["missing_outcomes"] == 0
        and status["missing_primary_moderators"] == 0
        and status["invalid_weights"] == 0
    )
    (OUT / "resistance_input_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if status["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


