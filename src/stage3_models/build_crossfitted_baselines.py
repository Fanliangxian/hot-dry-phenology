from __future__ import annotations

import json
import sys
from pathlib import Path
import os

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage6_baseline_repair_audit"
sys.path.insert(0, str(ROOT / "src"))

from baseline_repair import add_all_year_linear_loo, add_fixed_event_non_event_loo


SOURCE = (
    PROJECT / "stage1_window_baseline" / "results" / "fixed_window_runs"
    / "fixed_window_v01" / "events_with_latitude"
)
OUTPUT = ROOT / "results" / "candidate_pixel_year"
QC_TABLE = ROOT / "results" / "baseline_qc_by_candidate.csv"
DIAGNOSTICS = ROOT / "results" / "baseline_pairwise_diagnostics.csv"
STATUS = ROOT / "results" / "candidate_baseline_status.json"

SOURCE_COLUMNS = [
    "pixel_id", "year", "pheno_type", "landscape_type", "lat_band", "era_cell_id",
    "pheno_value", "anomaly_crossfit", "abs_anomaly_crossfit", "cell_index", "gap_days",
    "fixed_window_start", "fixed_window_end", "window_complete", "event_3d_occurrence",
    "event_3d_cumulative_days", "event_3d_max_duration", "latitude", "longitude",
    "lat_band_10deg",
]


def output_path(source_file: str) -> Path:
    source = Path(source_file)
    source_id = next(part for part in source.parts if part.startswith("source_id="))
    cell_bucket = next(part for part in source.parts if part.startswith("cell_bucket="))
    return OUTPUT / source_id / cell_bucket / "part.parquet"


def summarize(frame: pd.DataFrame, fragment: str) -> list[dict]:
    rows = []
    specs = [
        ("legacy_moving_event_non_event_loo", "anomaly_crossfit", "abs_anomaly_crossfit", None),
        ("all_year_linear_loo", "anomaly_all_year_linear_loo", "abs_anomaly_all_year_linear_loo", "method_all_year_linear_loo"),
        ("fixed_event_non_event_loo", "anomaly_fixed_event_non_event_loo", "abs_anomaly_fixed_event_non_event_loo", "method_fixed_event_non_event_loo"),
    ]
    for name, signed, absolute, method in specs:
        valid = frame[signed].notna()
        base = {
            "fragment": fragment,
            "candidate": name,
            "rows": len(frame),
            "valid_anomalies": int(valid.sum()),
            "missing_anomalies": int((~valid).sum()),
            "mean_signed_anomaly": float(frame.loc[valid, signed].mean()),
            "mean_abs_anomaly": float(frame.loc[valid, absolute].mean()),
        }
        if method is None:
            rows.append({**base, "method": "legacy_unspecified", "method_rows": int(valid.sum())})
        else:
            for label, count in frame[method].value_counts(dropna=False).items():
                rows.append({**base, "method": str(label), "method_rows": int(count)})
    return rows


def pairwise(frame: pd.DataFrame, fragment: str) -> list[dict]:
    rows = []
    pairs = [
        ("all_year_linear_loo", "anomaly_all_year_linear_loo"),
        ("fixed_event_non_event_loo", "anomaly_fixed_event_non_event_loo"),
    ]
    reference = frame["anomaly_crossfit"]
    for name, column in pairs:
        valid = reference.notna() & frame[column].notna()
        difference = frame.loc[valid, column] - reference.loc[valid]
        rows.append({
            "fragment": fragment,
            "candidate": name,
            "paired_rows": int(valid.sum()),
            "correlation_with_legacy": float(reference.loc[valid].corr(frame.loc[valid, column])),
            "mean_difference_days": float(difference.mean()),
            "median_difference_days": float(difference.median()),
            "q05_difference_days": float(difference.quantile(0.05)),
            "q95_difference_days": float(difference.quantile(0.95)),
            "mean_absolute_difference_days": float(difference.abs().mean()),
        })
    return rows


def main() -> int:
    if OUTPUT.exists() and any(OUTPUT.rglob("*.parquet")):
        raise FileExistsError(f"Candidate output already exists: {OUTPUT}")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dataset = ds.dataset(SOURCE, format="parquet", partitioning="hive")
    filt = ds.field("gap_days") == 0
    qc_rows: list[dict] = []
    diagnostic_rows: list[dict] = []
    total_rows = 0
    for index, fragment in enumerate(dataset.get_fragments(filter=filt), start=1):
        frame = fragment.to_table(columns=SOURCE_COLUMNS, filter=filt).to_pandas()
        if frame.duplicated(["pixel_id", "year", "pheno_type", "landscape_type"]).any():
            raise ValueError(f"Duplicate primary key in {fragment.path}")
        repaired = add_all_year_linear_loo(frame, min_linear_training=8)
        repaired = add_fixed_event_non_event_loo(
            repaired, min_non_event_linear=8, min_non_event_mean=3
        )
        target = output_path(fragment.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pandas(repaired, preserve_index=False), target, compression="zstd")
        qc_rows.extend(summarize(repaired, fragment.path))
        diagnostic_rows.extend(pairwise(repaired, fragment.path))
        total_rows += len(repaired)
        if index % 20 == 0:
            print(json.dumps({"fragments_complete": index, "rows": total_rows}), flush=True)

    qc = pd.DataFrame(qc_rows)
    diagnostics = pd.DataFrame(diagnostic_rows)
    qc.to_csv(QC_TABLE, index=False, encoding="utf-8-sig")
    diagnostics.to_csv(DIAGNOSTICS, index=False, encoding="utf-8-sig")
    candidate = ds.dataset(OUTPUT, format="parquet", partitioning="hive")
    status = {
        "source_gap0_rows": int(dataset.count_rows(filter=filt)),
        "output_rows": int(candidate.count_rows()),
        "fragments": len(candidate.files),
        "all_year_missing_anomalies": int(qc.loc[qc.candidate.eq("all_year_linear_loo")].groupby("fragment").missing_anomalies.first().sum()),
        "fixed_event_missing_anomalies": int(qc.loc[qc.candidate.eq("fixed_event_non_event_loo")].groupby("fragment").missing_anomalies.first().sum()),
    }
    status["row_count_preserved"] = status["source_gap0_rows"] == status["output_rows"]
    status["all_candidates_complete"] = (
        status["all_year_missing_anomalies"] == 0 and status["fixed_event_missing_anomalies"] == 0
    )
    STATUS.write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))
    return 0 if status["row_count_preserved"] and status["all_candidates_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


