# Compound hot–dry events and vegetation phenology

Code, lightweight source data, and reproducibility documentation for the study of pre-phenology compound hot–dry events in protected-area-dominated (PA) and urban-area-dominated (UA) landscapes across 20–60°N during 2001–2024.

> Repository status: manuscript-associated research compendium. The title, author list, journal citation, and DOI should be updated after acceptance.

## Scientific overview

The workflow links satellite-derived start and end of season (SOS/EOS) with compound hot–dry exposure during fixed 90-day pre-phenology windows. It separates:

1. event occurrence associations;
2. conditional cumulative-dose responses among event years; and
3. ecological heterogeneity in phenological resistance along precipitation and forest-cover gradients.

The primary analysis uses an event-independent, all-other-year linear leave-one-out phenology baseline; 5° × 5° and 10° × 10° Rademacher spatial-block score bootstraps quantify sensitivity to spatial dependence.

## Final figure order

- Fig. 1 — Study domain and analytical samples
- Fig. 2 — Spatial patterns of compound-event exposure and phenological shifts
- Fig. 3 — Latitude-dependent occurrence associations
- Fig. 4 — Conditional cumulative-dose response
- Fig. 5 — Shared gradients of resistance

PNG previews are in [`results/figures`](results/figures). Lightweight figure source data are in [`data/figure_source_data`](data/figure_source_data).

## Repository structure

```text
.
├── config/                    # Frozen statistical contracts
├── data/figure_source_data/   # Lightweight data used to draw final figures
├── docs/                      # Provenance, reproduction, and upload guidance
├── results/figures/           # Final PNG previews
├── scripts/                   # Release checks and convenience runners
├── src/
│   ├── stage1_exposure/       # Fixed-window event construction and weather QC
│   ├── stage2_covariates/     # Environmental/land-cover covariates and weighting
│   ├── stage3_models/         # Baseline repair and final statistical models
│   └── figures/               # Figure-generation code
└── tests/                     # Public-release integrity tests
```

## Quick start: reproduce figures

```bash
conda env create -f environment.yml
conda activate hot-dry-phenology
python scripts/reproduce_figures.py
```

Figure 2 additionally requires a Natural Earth low-resolution country-boundary shapefile. Set its path before running:

```bash
# Linux/macOS
export NATURAL_EARTH_SHP=/path/to/naturalearth_lowres.shp

# Windows PowerShell
$env:NATURAL_EARTH_SHP='D:\path\to\naturalearth_lowres.shp'
```

## Reproduce the complete analysis

The full model workflow requires large intermediate assets that are intentionally not stored in Git. Obtain the inputs described in [`DATA.md`](DATA.md), create the working-directory layout described in [`docs/REPRODUCIBILITY.md`](docs/REPRODUCIBILITY.md), and set:

```bash
export HOT_DRY_PROJECT_ROOT=/path/to/analysis-workspace
```

The final repaired workflow is represented by the scripts in `src/stage3_models`. The frozen contracts in `config/` define the primary exposure, baseline, dose contrast, moderators, weights, clustering, spatial bootstrap, and multiplicity rules.

The Google Earth Engine script used to export MCD12Q1 modal land cover is provided as `src/stage2_covariates/export_mcd12q1_landcover.js`; replace the placeholder asset root with assets in your own Earth Engine project.

## Core statistical definitions

- Compound day: daily Tmax and VPD both exceed their calendar-day 90th percentiles.
- Event: a run of at least three consecutive compound days; five-day runs are a sensitivity definition.
- Primary window: 90 days before the leave-one-year-out phenology anchor, with zero-day gap.
- Primary response baseline: linear leave-one-year-out model using all other valid years when at least eight are available; otherwise their mean.
- Outcome-model weight: analytical pixel count × overlap weight.
- Uncertainty: ERA5-cell clustered covariance plus 999 Rademacher spatial-block score-bootstrap replicates using 5° × 5° and 10° × 10° blocks.
- Interpretation: adjusted observational associations in the overlap-weighted analytical pixel population, not causal effects of urbanization or protection.

## Data availability and licensing

Raw third-party datasets are not redistributed here. Their sources, versions, access conditions, and derived-data boundaries are documented in [`DATA.md`](DATA.md).

Code is released under the MIT License. Repository-authored lightweight tabular source data are released under CC BY 4.0, subject to the licenses and citation requirements of their upstream datasets.

## Citation

Please cite the associated paper and this software release. Before publication, update [`CITATION.cff`](CITATION.cff) with the final authors, paper DOI, repository URL, and Zenodo DOI.

## Contact

Open a GitHub issue for reproducibility questions. Add the corresponding author's public contact information before making the repository public.
