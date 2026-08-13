# Public-release QA report

Date: 2026-08-12

## Outcome

The repository package passed the public-release integrity check and is ready for author metadata completion and user upload.

## Checks completed

- All public Python files parse successfully.
- No personal Windows drive path remains in public code/configuration.
- No private Google Earth Engine asset identifier or cloud-authentication secret marker was detected.
- No file approaches GitHub's 100 MB per-file limit.
- Core documentation, frozen configuration, modelling scripts, figure scripts, source-data tables, and PNG previews are present.
- Figure 1 and Figure 2 map scripts ran successfully when supplied with a Natural Earth shapefile.
- Figure 3, Figure 4, Figure 5, and the supplementary figure regenerated successfully from included CSV files.
- Bootstrap half-violin source tables contain the real 999-replicate draws used by the final plots.
- Manual execution of all three integrity-test functions passed.

## Environment note

The available bundled runtimes did not contain `pytest`, so `pytest -q` could not be executed in this preparation environment. The same test functions were imported and executed directly and all passed. The public `environment.yml` and `requirements.txt` include pytest, so the documented command will work after creating the repository environment.

## Author actions still required

1. Replace `YOUR_ACCOUNT` and generic author entries in `CITATION.cff`.
2. Add the corresponding author's public contact information.
3. Add the final paper title, author list, journal citation, paper DOI, and Zenodo DOI when available.
4. Confirm the intended MIT code license and CC BY 4.0 license for repository-authored source tables with all co-authors/institutional policy.
5. Review third-party data citations and redistribution terms once more before changing the repository from Private to Public.
