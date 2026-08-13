# Data sources and redistribution boundaries

Raw third-party data are not committed to this repository. Users must obtain them from the original providers and comply with their terms.

| Asset | Version / period | Role | Public source | Included here? |
|---|---|---|---|---|
| MODIS NDVI | MOD13C1 V6.1, 2001–2024 | Annual SOS/EOS derivation | NASA LP DAAC | No |
| Derived phenology | 2000–2024 release | Pixel-year SOS/EOS | https://doi.org/10.6084/m9.figshare.33152885 | No; download from Figshare |
| ERA5-Land daily statistics | 2001–2024 | Tmax, mean temperature, dewpoint/VPD, event exposure | Copernicus Climate Data Store | No |
| GAIA | 2000 urban extent | Long-established urban domain | Original GAIA data provider/publication | No |
| WDPA | Study download/version | Protected-area boundaries established before 2001 | Protected Planet | No; redistribution may be restricted |
| WorldClim | v2.1, 1970–2000, 10 arc-min | Precipitation climatology and elevation | https://www.worldclim.org/data/worldclim21.html | No |
| MCD12Q1 | v061 LC_Type1, 2001–2023 | Modal IGBP land-cover composition | Google Earth Engine / NASA LP DAAC | No raw export |
| Natural Earth | low-resolution countries | Figure 2 basemap only | https://www.naturalearthdata.com/ | No |

## Included derived source data

`data/figure_source_data/` contains lightweight tables supporting the final figures. The tables contain aggregated/model-derived values and bootstrap draws, not raw satellite imagery or third-party vector boundaries.

Important filename mapping after the final figure renumbering:

- `Figure1a.csv`–`Figure1c.csv` → final Figure 1
- `FigureS1_spatial_patterns.csv` → final Figure 2
- `Figure2_SourceData.csv` and `Figure3_spatial_bootstrap_draws.csv` → final Figure 3
- `Figure3a.csv`, `Figure3bc.csv`, `Figure3d.csv`, `Figure3d_shape.csv` → final Figure 4
- `Figure4ab.csv`–`Figure4f.csv` and `Figure5_resistance_bootstrap_draws.csv` → final Figure 5

## Files deliberately excluded

- daily ERA5 Zarr stores;
- raw and intermediate Parquet datasets;
- Google Earth Engine credentials and private asset IDs;
- WDPA/GAIA vector files;
- unpublished manuscript drafts and author metadata;
- superseded pre-baseline-repair numerical results.

## Integrity recommendation

For archival publication, deposit any shareable processed model-input datasets in Figshare or Zenodo and record SHA-256 checksums and persistent DOIs here. Do not use Git LFS as a substitute for checking third-party redistribution rights.
