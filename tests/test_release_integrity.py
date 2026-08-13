from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]


def test_core_files_exist():
    expected = [
        "README.md", "DATA.md", "config/baseline_repair_spec.json",
        "data/figure_source_data/Figure3_spatial_bootstrap_draws.csv",
        "data/figure_source_data/Figure5_resistance_bootstrap_draws.csv",
        "results/figures/Figure5_ecological_resistance.png",
    ]
    assert all((ROOT / item).exists() for item in expected)


def test_public_python_parses():
    failures = []
    for path in ROOT.rglob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8-sig"))
        except SyntaxError as exc:
            failures.append((str(path.relative_to(ROOT)), str(exc)))
    assert not failures


def test_no_file_exceeds_github_limit():
    large = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*")
             if p.is_file() and p.stat().st_size >= 100 * 1024 * 1024]
    assert not large
