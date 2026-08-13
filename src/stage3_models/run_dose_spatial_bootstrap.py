from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
import os

import pyarrow.dataset as ds


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage6_baseline_repair_audit" / "full_propagation"
INPUT = ROOT / "model_input" / "dose"
OUT = ROOT / "results" / "dose"
MODEL_SCRIPT = PROJECT / "stage3_dose_response" / "scripts" / "run_dose_models.py"
BOOT_SCRIPT = PROJECT / "stage3_dose_response" / "scripts" / "run_dose_spatial_bootstrap.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MODELS = load_module("run_dose_models", MODEL_SCRIPT)
MODELS.INPUT = INPUT
MODELS.OUT = OUT


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


MODELS.load_partition = load_partition
sys.modules["run_dose_models"] = MODELS
BOOT = load_module("full_dose_bootstrap", BOOT_SCRIPT)


def main() -> int:
    BOOT.main()
    status = json.loads((OUT / "dose_spatial_bootstrap_status.json").read_text(encoding="utf-8"))
    validation = {
        "baseline": "all_year_linear_loo",
        "rows_expected": 96,
        "rows": status["rows"],
        "failures": status["failures"],
        "replicates": status["replicates"],
        "all_checks_pass": bool(status["all_success"]),
    }
    (OUT / "dose_full_spatial_status.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))
    return 0 if validation["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


