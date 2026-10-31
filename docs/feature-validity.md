# Feature-validity diagnostic

The diagnostic checks whether stored fields and collection conditions need further investigation before a final evaluation protocol is chosen. It profiles the fourteen FLNET DDoS/Normal development CSVs and reuses an existing engineering subset. It never opens reserved test CSVs.

## Procedure

Run `uv run python scripts/audit_feature_validity.py` after the portable engineering check. The default prepared run is `engineering-smoke-v1-portable`; `--engineering-run engineering-smoke-v1` explicitly selects the historical preparation when its original artifacts and manifest are available. Both routes verify preparation hashes and source identities.

The program computes numeric extrema, negative-value counts, zero counts, and nonfinite counts for each field and label. It also records stored dates, constants, and whether positive-duration rows satisfy the arithmetic relation `flow_duration * flow_pkts_s = 1e6 * (tot_fwd_pkts + tot_bwd_pkts)` within relative tolerance `1e-6`. This arithmetic check alone does not verify physical units or identify the extractor used by a publisher. Zero-duration rows are reported separately.

Three prespecified fields, `flow_duration`, `tot_fwd_pkts`, and `tot_bwd_pkts`, each receive a separate depth-one decision tree. Missing fields in a synthetic fixture are skipped. Each tree is fitted using the engineering subset's fitting rows only, with default unweighted Gini impurity and seed 20261031. Validation rows do not choose its threshold. The program reports fitting and validation confusion counts, recall, false-positive rate, and average precision. Average precision uses scores; recall and average precision remain undefined without attack support.

These checks are exploratory. They reuse an already examined development subset and do not form an independent test or a final feature-selection procedure. A high score from one field warrants investigation but does not by itself prove leakage or an extraction defect. Capture independence, collection conditions, extractor configuration, and the intended deployment claim still require separate evidence. No cleaning, relabeling, feature removal, final split assignment, or benchmark optimizer comparison takes place.

## Outputs and preservation

Outputs live under `reports/development-preparation/feature-validity-v1/` in the private workspace. `feature-profiles.csv` contains the field summaries; `summary.json` contains the diagnostics, source hashes, subset identity, environment, and limitations. `COMPLETE.json` records output hashes, both local source-file hashes, and the dependency-lock hash. An existing output directory causes refusal, including a directory left by an interrupted run. Preserve that evidence and use a new reviewed version for a changed procedure.

The profiler scans CSVs in chunks, but the selected engineering subset is loaded in memory. No bound on an arbitrary user's prepared Parquet file is claimed. For the intended workflow, the subset is produced by the bounded engineering program. Unit tests verify numeric extrema, chunk aggregation, exclusion of validation data from threshold fitting, group-overlap rejection, rate handling, and rejection of a reserved path even when incorrectly marked as development. The synthetic integration workflow exercises the command with poisoned reserved test contents and checks refusal to overwrite.

## Source interpretation

Kumar et al. (2023), Section III-C, identify CICFlowMeter as the extractor but do not specify its exact commit or configuration. Their paper and the current release must be checked independently when reconstructing a feature dictionary. The [CIC documentation](https://www.unb.ca/cic/research/applications.html) explains the intended bidirectional flow model. Do not assume that a similarly named implementation reproduces the release.

When citing this diagnostic in a thesis, link `scripts/audit_feature_validity.py` at the actual executed commit, identify the private run record, and retain its source hashes. A later edited script is not evidence for an earlier result.

Kumar, P., Liu, J., Tayeen, A. S. M., Misra, S., Cao, H., Harikumar, J., & Perez, O. (2023). FLNET2023: Realistic network intrusion detection dataset for federated learning. In *MILCOM 2023* (pp. 345-350). IEEE. https://doi.org/10.1109/MILCOM58377.2023.10356272
