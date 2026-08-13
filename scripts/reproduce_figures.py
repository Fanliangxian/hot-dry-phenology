from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIGURE_SCRIPTS = [
    ("Figure 1", ROOT / "src/figures/plot_figure1.py", "NATURAL_EARTH_SHP"),
    ("Figure 2", ROOT / "src/figures/plot_figure2.py", "NATURAL_EARTH_SHP"),
    ("Figure 3", ROOT / "src/figures/plot_figure3.py", None),
    ("Figure 4", ROOT / "src/figures/plot_figure4.py", None),
    ("Figure 5", ROOT / "src/figures/plot_figure5.py", None),
    ("Supplementary figure", ROOT / "src/figures/plot_supplementary_figure.py", None),
]


def main() -> int:
    failures = []
    for label, script, required_env in FIGURE_SCRIPTS:
        if required_env and not os.environ.get(required_env):
            print(f"SKIP {label}: set {required_env} to enable the map baselayer")
            continue
        print(f"RUN  {label}: {script.relative_to(ROOT)}")
        result = subprocess.run([sys.executable, str(script)], cwd=ROOT, check=False)
        if result.returncode:
            failures.append((label, result.returncode))
    if failures:
        print(f"Failed: {failures}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
