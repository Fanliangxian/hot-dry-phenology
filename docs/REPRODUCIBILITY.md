# Reproducibility guide

## Two supported levels

### Level 1 — Figure reproduction

This level uses the included CSV files and should run on a normal workstation. Install the environment and execute `python scripts/reproduce_figures.py`.

### Level 2 — Complete model reproduction

This level rebuilds exposures, covariates, cross-fitted baselines, occurrence models, dose models, resistance models, and spatial bootstraps. It requires the external assets in `DATA.md` and substantial memory/storage.

## Recommended execution order

1. `src/stage1_exposure/audit_weather_coverage.py`
2. `src/stage1_exposure/recompute_fixed_window_events.py`
3. `src/stage2_covariates/acquire_worldclim_assets.py`
4. `src/stage2_covariates/build_environmental_covariates.py`
5. Export MCD12Q1 point samples in Earth Engine, then run `merge_mcd12q1_exports.py`.
6. `src/stage2_covariates/fit_propensity_and_occurrence_models.py`
7. `src/stage3_models/build_crossfitted_baselines.py`
8. `src/stage3_models/build_model_inputs.py`
9. Run occurrence, dose, and resistance model scripts, followed by their spatial-bootstrap scripts.
10. Regenerate figure source data and figures.

## Path configuration

Analysis scripts read `HOT_DRY_PROJECT_ROOT`. It must point to a workspace containing the expected stage directories and externally downloaded data. No personal drive path is required by the public copy.

## Frozen primary design

The JSON files in `config/` are the authoritative contracts. In particular, do not change the 3-vs-10-day dose contrast, spline dimensions, key latitudes, weight, spatial-block sizes, random seed, or multiplicity families when attempting exact reproduction.

## Computational notes

- Python 3.11 or 3.12 is recommended.
- Full exposure data use chunked Parquet/Zarr operations.
- The full spatial bootstrap uses 999 repetitions per contrast and may take several minutes to hours depending on hardware.
- The bootstrap random seed is 20260807.

## Expected verification

Run:

```bash
python scripts/check_release.py
pytest -q
```

For an exact analytical rerun, compare generated QC/status JSON files, row counts, model counts, failed-model counts, and frozen contrast tables—not only the appearance of figures.
