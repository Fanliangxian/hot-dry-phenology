from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import os

import pyarrow.dataset as ds


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage6_baseline_repair_audit" / "full_propagation"
INPUT = ROOT / "model_input" / "dose"
OUT = ROOT / "results" / "dose"
BASE_SCRIPT = PROJECT / "stage3_dose_response" / "scripts" / "run_dose_models.py"


def load_base():
    spec = importlib.util.spec_from_file_location("full_dose_base", BASE_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


BASE = load_base()
BASE.INPUT = INPUT
BASE.OUT = OUT


def load_partition(gap: int, duration: int, metric: str, pheno: str):
    dataset = ds.dataset(INPUT, format="parquet")
    filt = (
        (ds.field("gap_days") == gap) & (ds.field("event_min_days") == duration)
        & (ds.field("dose_metric") == metric) & (ds.field("pheno_type") == pheno)
    )
    frame = dataset.to_table(filter=filt).to_pandas()
    if frame.empty:
        raise ValueError(f"Empty repaired dose partition: {(gap, duration, metric, pheno)}")
    frame["mean_anomaly_crossfit"] = frame.mean_anomaly_all_year_linear_loo
    frame["mean_abs_anomaly_crossfit"] = frame.mean_abs_anomaly_all_year_linear_loo
    return frame


BASE.load_partition = load_partition


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    BASE.main()
    status = json.loads((OUT / "dose_model_run_status.json").read_text(encoding="utf-8"))
    validation = {
        "baseline": "all_year_linear_loo",
        "models_expected": 60,
        "models_fit": status["models_fit"],
        "model_failures": status["model_failures"],
        "global_test_rows": status["global_test_rows"],
        "local_contrast_rows": status["local_contrast_rows"],
        "curve_rows": status["curve_rows"],
    }
    validation["all_checks_pass"] = validation["models_fit"] == 60 and validation["model_failures"] == 0
    (OUT / "dose_full_status.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))
    return 0 if validation["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


