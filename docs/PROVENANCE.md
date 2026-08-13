# Code provenance and scope

This public package was distilled from the final repaired analysis chain on 12 August 2026.

## Included stages

- fixed-window event construction and weather coverage audit;
- WorldClim and MCD12Q1 covariate preparation;
- latitude-stratified propensity modelling and overlap weighting;
- event-independent cross-fitted baseline construction;
- final occurrence, dose-response, resistance, and spatial-bootstrap models;
- final Figure 2–5 and supplementary plotting workflows;
- lightweight final figure source data, including real 999-replicate bootstrap draws used for half-violin displays.

## Excluded or superseded material

Earlier numerical results generated before the all-other-year baseline repair are not included. Exploratory notebooks, manuscript drafts, temporary previews, caches, and large intermediates are also excluded. The public package is therefore a curated research compendium, not a byte-for-byte copy of the private working directory.

## Important reproducibility boundary

Some upstream spatial-sample construction operations (GAIA urban buffering, WDPA geometry processing, and the original phenology-product QA workflow) depend on externally maintained assets and processing provenance. The repository documents these inputs but does not claim to redistribute them. These provenance limitations should also be stated in the manuscript or supplementary methods.
