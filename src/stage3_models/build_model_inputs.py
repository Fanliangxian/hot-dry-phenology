from __future__ import annotations

import json
from pathlib import Path
import os

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage6_baseline_repair_audit"
FULL = ROOT / "full_propagation"
SOURCE = (
    PROJECT / "stage1_window_baseline" / "results" / "fixed_window_runs"
    / "fixed_window_v01" / "events_with_latitude"
)
REPAIRED = ROOT / "results" / "candidate_pixel_year"
OCC_REFERENCE = (
    PROJECT / "stage2_covariate_inventory" / "stage2b_landcover" / "results"
    / "stage2b_landcover_model_input.parquet"
)
DOSE_REFERENCE = PROJECT / "stage3_dose_response" / "results" / "dose_model_input"
WEATHER_QC = (
    PROJECT / "stage1_window_baseline" / "results" / "fixed_window_runs"
    / "fixed_window_v01" / "weather_coverage_qc.json"
)
INTER_OCC = FULL / "intermediate" / "occurrence"
INTER_DOSE = FULL / "intermediate" / "dose"
MODEL_INPUT = FULL / "model_input"
OUT_OCC = MODEL_INPUT / "occurrence"
OUT_DOSE = MODEL_INPUT / "dose"

KEY = ["pixel_id", "year", "pheno_type", "landscape_type"]
OCC_KEYS = [
    "gap_days", "event_min_days", "pheno_type", "landscape_type",
    "lat_band_10deg", "era_cell_id", "year", "event",
]
DOSE_KEYS = [
    "gap_days", "event_min_days", "dose_metric", "pheno_type",
    "era_cell_id", "landscape_type", "year", "dose", "boundary_truncated",
]
SOURCE_COLUMNS = [
    "pixel_id", "year", "pheno_type", "landscape_type", "era_cell_id", "cell_index",
    "gap_days", "window_complete", "event_3d_occurrence", "event_3d_cumulative_days",
    "event_3d_max_duration", "event_5d_occurrence", "event_5d_cumulative_days",
    "event_5d_max_duration", "latitude", "lat_band_10deg",
]
REPAIR_COLUMNS = KEY + ["anomaly_all_year_linear_loo", "abs_anomaly_all_year_linear_loo"]


def repaired_path(fragment_path: str) -> Path:
    parts = Path(fragment_path).parts
    source_id = next(part for part in parts if part.startswith("source_id="))
    bucket = next(part for part in parts if part.startswith("cell_bucket="))
    return REPAIRED / source_id / bucket / "part.parquet"


def aggregate(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    frame["sum_anomaly_all_year_linear_loo"] = frame.anomaly_all_year_linear_loo.fillna(0.0)
    frame["sum_abs_anomaly_all_year_linear_loo"] = frame.abs_anomaly_all_year_linear_loo.fillna(0.0)
    frame["n_anomaly_all_year_linear_loo"] = frame.anomaly_all_year_linear_loo.notna().astype("int32")
    frame["n_abs_anomaly_all_year_linear_loo"] = frame.abs_anomaly_all_year_linear_loo.notna().astype("int32")
    return frame.groupby(keys, observed=True, sort=False, dropna=False).agg(
        n_pixels_repaired=("pixel_id", "size"),
        sum_anomaly_all_year_linear_loo=("sum_anomaly_all_year_linear_loo", "sum"),
        sum_abs_anomaly_all_year_linear_loo=("sum_abs_anomaly_all_year_linear_loo", "sum"),
        n_anomaly_all_year_linear_loo=("n_anomaly_all_year_linear_loo", "sum"),
        n_abs_anomaly_all_year_linear_loo=("n_abs_anomaly_all_year_linear_loo", "sum"),
    ).reset_index()


def write_part(frame: pd.DataFrame, root: Path, partition: dict[str, object], index: int) -> None:
    target = root
    for key, value in partition.items():
        target = target / f"{key}={value}"
    target.mkdir(parents=True, exist_ok=True)
    pq.write_table(
        pa.Table.from_pandas(frame, preserve_index=False),
        target / f"part-{index:03d}.parquet",
        compression="zstd",
    )


def build_intermediate() -> dict:
    if any(INTER_OCC.rglob("*.parquet")) or any(INTER_DOSE.rglob("*.parquet")):
        raise FileExistsError("Full-propagation intermediate files already exist")
    dataset = ds.dataset(SOURCE, format="parquet", partitioning="hive")
    bad_cells = set(json.loads(WEATHER_QC.read_text(encoding="utf-8"))["used_bad_cell_indices"])
    source_rows = joined_rows = occurrence_pixel_rows = dose_pixel_rows = 0
    for index, fragment in enumerate(dataset.get_fragments(), start=1):
        source = fragment.to_table(columns=SOURCE_COLUMNS).to_pandas()
        repaired = pd.read_parquet(repaired_path(fragment.path), columns=REPAIR_COLUMNS)
        if repaired.duplicated(KEY).any():
            raise ValueError(f"Duplicate repaired key: {fragment.path}")
        frame = source.merge(repaired, on=KEY, how="left", validate="many_to_one", indicator=True)
        if not frame._merge.eq("both").all():
            raise ValueError(f"Unmatched repaired rows in {fragment.path}: {(frame._merge != 'both').sum()}")
        frame = frame.drop(columns="_merge")
        source_rows += len(source)
        joined_rows += len(frame)
        domain = frame.window_complete.fillna(False) & frame.latitude.between(20, 60, inclusive="left")

        occ_base = frame[domain & ~frame.cell_index.isin(bad_cells)].copy()
        occ_base["lat_band_10deg"] = occ_base.lat_band_10deg.astype(str)
        for duration in [3, 5]:
            occurrence = occ_base.copy()
            occurrence["event_min_days"] = np.int8(duration)
            occurrence["event"] = occurrence[f"event_{duration}d_occurrence"].astype("int8")
            for (gap, pheno), part in occurrence.groupby(["gap_days", "pheno_type"], observed=True):
                aggregated = aggregate(part, OCC_KEYS)
                occurrence_pixel_rows += int(aggregated.n_pixels_repaired.sum())
                write_part(
                    aggregated, INTER_OCC,
                    {"gap_days": int(gap), "event_min_days": duration, "pheno_type": pheno},
                    index,
                )

        dose_base = frame[domain].copy()
        for duration in [3, 5]:
            event_rows = dose_base[dose_base[f"event_{duration}d_occurrence"].eq(1)].copy()
            event_rows["event_min_days"] = np.int8(duration)
            event_rows["boundary_truncated"] = event_rows[f"event_{duration}d_max_duration"].lt(duration)
            for metric in ["cumulative_days", "max_duration"]:
                dose = event_rows.copy()
                dose["dose_metric"] = metric
                dose["dose"] = dose[f"event_{duration}d_{metric}"].astype("int16")
                for (gap, pheno), part in dose.groupby(["gap_days", "pheno_type"], observed=True):
                    aggregated = aggregate(part, DOSE_KEYS)
                    dose_pixel_rows += int(aggregated.n_pixels_repaired.sum())
                    write_part(
                        aggregated, INTER_DOSE,
                        {
                            "gap_days": int(gap), "event_min_days": duration,
                            "dose_metric": metric, "pheno_type": pheno,
                        },
                        index,
                    )
        if index % 20 == 0:
            print(json.dumps({"fragments": index, "source_rows": source_rows}), flush=True)
    return {
        "source_rows": source_rows,
        "joined_rows": joined_rows,
        "occurrence_event_definition_pixel_rows": occurrence_pixel_rows,
        "dose_metric_pixel_rows": dose_pixel_rows,
    }


def collapse_partition(root: Path, keys: list[str], filt) -> pd.DataFrame:
    # Partition keys are retained as physical columns in every intermediate file.
    # Reading without hive inference avoids int8/int32 schema conflicts.
    dataset = ds.dataset(root, format="parquet")
    frame = dataset.to_table(filter=filt).to_pandas()
    numeric = [column for column in frame.columns if column not in keys]
    return frame.groupby(keys, observed=True, sort=False, dropna=False)[numeric].sum().reset_index()


def add_means(frame: pd.DataFrame) -> pd.DataFrame:
    frame["mean_anomaly_all_year_linear_loo"] = (
        frame.sum_anomaly_all_year_linear_loo / frame.n_anomaly_all_year_linear_loo.replace(0, np.nan)
    )
    frame["mean_abs_anomaly_all_year_linear_loo"] = (
        frame.sum_abs_anomaly_all_year_linear_loo / frame.n_abs_anomaly_all_year_linear_loo.replace(0, np.nan)
    )
    return frame


def finalize() -> tuple[pd.DataFrame, dict]:
    if any(OUT_OCC.rglob("*.parquet")) or any(OUT_DOSE.rglob("*.parquet")):
        raise FileExistsError("Full-propagation final model inputs already exist")
    occ_reference = ds.dataset(OCC_REFERENCE, format="parquet")
    dose_reference = ds.dataset(DOSE_REFERENCE, format="parquet", partitioning="hive")
    audits = []
    output_rows = 0
    for gap in [0, 8, 16]:
        for duration in [3, 5]:
            for pheno in ["SOS", "EOS"]:
                filt = (
                    (ds.field("gap_days") == gap) & (ds.field("event_min_days") == duration)
                    & (ds.field("pheno_type") == pheno)
                )
                repaired = add_means(collapse_partition(INTER_OCC, OCC_KEYS, filt))
                reference = occ_reference.to_table(filter=filt).to_pandas()
                reference["lat_band_10deg"] = reference.lat_band_10deg.astype(str)
                extra = repaired.merge(reference[OCC_KEYS], on=OCC_KEYS, how="left", indicator=True)
                repair_only = int(extra._merge.eq("left_only").sum())
                merged = reference.merge(repaired, on=OCC_KEYS, how="left", validate="one_to_one", indicator=True)
                unmatched = int((merged._merge != "both").sum())
                pixel_mismatch = int((merged.n_pixels != merged.n_pixels_repaired).sum())
                missing = int(merged[["mean_anomaly_all_year_linear_loo", "mean_abs_anomaly_all_year_linear_loo"]].isna().sum().sum())
                merged = merged.drop(columns="_merge")
                write_part(merged, OUT_OCC, {"gap_days": gap, "event_min_days": duration, "pheno_type": pheno}, 0)
                output_rows += len(merged)
                audits.append({
                    "input": "occurrence", "gap_days": gap, "event_min_days": duration,
                    "dose_metric": "", "pheno_type": pheno, "rows": len(merged),
                    "unmatched_keys": unmatched, "pixel_count_mismatches": pixel_mismatch,
                    "missing_outcomes": missing, "repair_only_groups_excluded": repair_only,
                })

            for metric in ["cumulative_days", "max_duration"]:
                for pheno in ["SOS", "EOS"]:
                    filt = (
                        (ds.field("gap_days") == gap) & (ds.field("event_min_days") == duration)
                        & (ds.field("dose_metric") == metric) & (ds.field("pheno_type") == pheno)
                    )
                    repaired = add_means(collapse_partition(INTER_DOSE, DOSE_KEYS, filt))
                    reference = dose_reference.to_table(filter=filt).to_pandas()
                    extra = repaired.merge(reference[DOSE_KEYS], on=DOSE_KEYS, how="left", indicator=True)
                    repair_only = int(extra._merge.eq("left_only").sum())
                    merged = reference.merge(repaired, on=DOSE_KEYS, how="left", validate="one_to_one", indicator=True)
                    unmatched = int((merged._merge != "both").sum())
                    pixel_mismatch = int((merged.n_pixels != merged.n_pixels_repaired).sum())
                    missing = int(merged[["mean_anomaly_all_year_linear_loo", "mean_abs_anomaly_all_year_linear_loo"]].isna().sum().sum())
                    merged = merged.drop(columns="_merge")
                    write_part(
                        merged, OUT_DOSE,
                        {
                            "gap_days": gap, "event_min_days": duration,
                            "dose_metric": metric, "pheno_type": pheno,
                        }, 0,
                    )
                    output_rows += len(merged)
                    audits.append({
                        "input": "dose", "gap_days": gap, "event_min_days": duration,
                        "dose_metric": metric, "pheno_type": pheno, "rows": len(merged),
                        "unmatched_keys": unmatched, "pixel_count_mismatches": pixel_mismatch,
                        "missing_outcomes": missing, "repair_only_groups_excluded": repair_only,
                    })
    audit = pd.DataFrame(audits)
    status = {
        "final_partitions": len(audit),
        "final_rows": output_rows,
        "unmatched_keys": int(audit.unmatched_keys.sum()),
        "pixel_count_mismatches": int(audit.pixel_count_mismatches.sum()),
        "missing_outcomes": int(audit.missing_outcomes.sum()),
        "repair_only_groups_excluded": int(audit.repair_only_groups_excluded.sum()),
    }
    status["all_checks_pass"] = all(status[key] == 0 for key in [
        "unmatched_keys", "pixel_count_mismatches", "missing_outcomes"
    ]) and len(audit) == 36
    return audit, status


def main() -> int:
    MODEL_INPUT.mkdir(parents=True, exist_ok=True)
    intermediate = build_intermediate()
    audit, status = finalize()
    audit.to_csv(MODEL_INPUT / "input_qc.csv", index=False, encoding="utf-8-sig")
    status = {**intermediate, **status}
    (MODEL_INPUT / "input_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if status["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


