from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
import os


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage6_baseline_repair_audit" / "full_propagation"
INPUT = ROOT / "model_input" / "resistance"
OUT = ROOT / "results" / "resistance"
MODEL_SCRIPT = PROJECT / "stage4_resistance_heterogeneity" / "scripts" / "run_resistance_models.py"
BOOT_SCRIPT = PROJECT / "stage4_resistance_heterogeneity" / "scripts" / "run_resistance_spatial_bootstrap.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


MODELS = load_module("run_resistance_models", MODEL_SCRIPT)
MODELS.INPUT = INPUT
MODELS.OUT = OUT
sys.modules["run_resistance_models"] = MODELS
BOOT = load_module("full_resistance_bootstrap", BOOT_SCRIPT)


def main() -> int:
    BOOT.main()
    status = json.loads((OUT / "resistance_spatial_bootstrap_status.json").read_text(encoding="utf-8"))
    validation = {
        "baseline": "all_year_linear_loo", "rows_expected": 112,
        "rows": status["rows"], "failures": status["failures"],
        "replicates": status["replicates"], "all_checks_pass": bool(status["all_success"]),
    }
    (OUT / "resistance_full_spatial_status.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))
    return 0 if validation["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


