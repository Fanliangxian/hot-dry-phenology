from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import os
import json

import pandas as pd
import pyarrow.dataset as ds


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage3_dose_response"
SOURCE = (PROJECT / "stage1_window_baseline" / "results" / "fixed_window_runs" /
          "fixed_window_v01" / "events_with_latitude")
SPEC_PATH = ROOT / "config" / "dose_model_spec.json"
OUT = ROOT / "audit" / "dose_contrast_support.csv"
DOMAIN_BANDS = ["20-30N", "30-40N", "40-50N", "50-60N"]


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    families = spec["metric_families"]
    columns = ["gap_days", "pheno_type", "landscape_type", "lat_band_10deg",
               "era_cell_id", "window_complete"]
    for family in families:
        duration = family["event_min_days"]
        metric = family["metric"]
        columns.extend([f"event_{duration}d_occurrence", f"event_{duration}d_{metric}"])
    columns = list(dict.fromkeys(columns))

    counts: Counter[tuple] = Counter()
    cells: dict[tuple, set[str]] = defaultdict(set)
    dataset = ds.dataset(SOURCE, format="parquet")
    for batch in dataset.to_batches(columns=columns, batch_size=500_000):
        frame = batch.to_pandas()
        frame = frame[
            frame.window_complete.fillna(False) &
            frame.lat_band_10deg.astype(str).isin(DOMAIN_BANDS) &
            frame.gap_days.isin([0, 8, 16])
        ]
        for family in families:
            duration, metric = family["event_min_days"], family["metric"]
            occurrence = f"event_{duration}d_occurrence"
            dose = f"event_{duration}d_{metric}"
            event = frame[frame[occurrence] == 1]
            for point_name in ["low", "high"]:
                point = family[point_name]
                selected = event[event[dose] == point]
                group_cols = ["gap_days", "pheno_type", "landscape_type", "lat_band_10deg"]
                for keys, group in selected.groupby(group_cols, observed=True, sort=False):
                    key = (*keys, duration, metric, point_name, point)
                    counts[key] += len(group)
                    cells[key].update(group.era_cell_id.dropna().astype(str).unique())

    rows = []
    for gap in [0, 8, 16]:
        for pheno in ["SOS", "EOS"]:
            for landscape in ["PA", "UA"]:
                for band in DOMAIN_BANDS:
                    for family in families:
                        for point_name in ["low", "high"]:
                            point = family[point_name]
                            key = (gap, pheno, landscape, band, family["event_min_days"],
                                   family["metric"], point_name, point)
                            row_count = counts[key]
                            cell_count = len(cells[key])
                            rows.append({
                                "gap_days": gap,
                                "event_min_days": family["event_min_days"],
                                "pheno_type": pheno,
                                "landscape_type": landscape,
                                "lat_band_10deg": band,
                                "metric": family["metric"],
                                "contrast_point": point_name,
                                "dose_value": point,
                                "raw_event_rows": row_count,
                                "era_cells": cell_count,
                                "support_pass": bool(row_count >= 100 and cell_count >= 30),
                            })
    output = pd.DataFrame(rows)
    output.to_csv(OUT, index=False, encoding="utf-8-sig")
    summary = {
        "rows": len(output),
        "all_support_pass": bool(output.support_pass.all()),
        "minimum_raw_event_rows": int(output.raw_event_rows.min()),
        "minimum_era_cells": int(output.era_cells.min()),
        "failed_rows": int((~output.support_pass).sum()),
    }
    (ROOT / "audit" / "dose_contrast_support_qc.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()



