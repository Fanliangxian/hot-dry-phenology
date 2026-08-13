from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".py", ".js", ".md", ".json", ".yaml", ".yml", ".cff", ".txt", ".csv"}
REQUIRED = [
    "README.md", "DATA.md", "LICENSE", "CITATION.cff", "environment.yml",
    "docs/REPRODUCIBILITY.md", "docs/GITHUB_UPLOAD_TUTORIAL_CN.md",
    "src/stage3_models/run_occurrence_models.py",
    "src/stage3_models/run_dose_models.py",
    "src/stage3_models/run_resistance_models.py",
    "src/figures/plot_figure3.py", "src/figures/plot_figure5.py",
]
FORBIDDEN = [
    re.compile(r"[A-Za-z]:[\\/](?:Users|Research)[\\/]", re.I),
    re.compile(r"projects/ee-[^/\s]+/assets", re.I),
    re.compile(r"service[_-]?account", re.I),
    re.compile(r"private[_-]?key", re.I),
]


def main() -> int:
    errors = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            errors.append(f"missing required file: {rel}")
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        if path.stat().st_size > 95 * 1024 * 1024:
            errors.append(f"oversized file: {path.relative_to(ROOT)}")
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"LICENSE", "LICENSE-DATA"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in FORBIDDEN:
                if pattern.search(text):
                    errors.append(f"forbidden local/private pattern in {path.relative_to(ROOT)}")
                    break
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            except SyntaxError as exc:
                errors.append(f"Python syntax error in {path.relative_to(ROOT)}: {exc}")
    if errors:
        print("RELEASE CHECK FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("RELEASE CHECK PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
