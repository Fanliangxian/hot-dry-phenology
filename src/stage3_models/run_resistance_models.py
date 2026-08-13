from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import os


PROJECT = Path(os.environ.get("HOT_DRY_PROJECT_ROOT", Path.cwd()))
ROOT = PROJECT / "stage6_baseline_repair_audit" / "full_propagation"
INPUT = ROOT / "model_input" / "resistance"
OUT = ROOT / "results" / "resistance"
BASE_SCRIPT = PROJECT / "stage4_resistance_heterogeneity" / "scripts" / "run_resistance_models.py"


spec = importlib.util.spec_from_file_location("full_resistance_base", BASE_SCRIPT)
BASE = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(BASE)
BASE.INPUT = INPUT
BASE.OUT = OUT


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    BASE.main()
    status = json.loads((OUT / "resistance_model_run_status.json").read_text(encoding="utf-8"))
    validation = {
        "baseline": "all_year_linear_loo",
        "models_expected": 24, "models_fit": status["models_fit"],
        "failures": status["failures"], "global_tests": status["global_tests"],
        "local_contrasts": status["local_contrasts"], "curve_rows": status["curve_rows"],
    }
    validation["all_checks_pass"] = validation["models_fit"] == 24 and validation["failures"] == 0
    (OUT / "resistance_full_status.json").write_text(json.dumps(validation, indent=2), encoding="utf-8")
    print(json.dumps(validation, indent=2))
    return 0 if validation["all_checks_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())


