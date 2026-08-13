# Contributing

Bug reports and reproducibility questions are welcome through GitHub Issues.

For code changes:

1. create a branch;
2. preserve the frozen primary statistical contracts unless the change is explicitly labelled as a new sensitivity analysis;
3. run `python scripts/check_release.py` and `pytest -q`;
4. document changes to estimands, exclusions, weights, random seeds, or multiplicity families;
5. do not commit raw restricted datasets, credentials, private asset IDs, or personal absolute paths.
