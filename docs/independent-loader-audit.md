# Independent candidate audit and purpose-filtered views

This module checks a prepared development candidate without fitting a scaler, selecting a detector, or fitting, scoring or calibrating a model. It adds an independent CSV conversion check and exact stored-record multiplicity accounting. The loader and AF-BKM adapter remain unchanged. Successful checks support engineering use of the candidate; they do not freeze the scientific protocol or establish physical flow semantics.

The code uses the installed Pandas C parser instead of the loader's `csv.reader` and NumPy string conversion. Context7 documentation was checked for `read_csv` with an explicit float64 dtype, `float_precision="round_trip"`, chunks, NA handling and bad-line policy. The available versioned Pandas docs were 3.0.6; the installed 3.0.3 signature and synthetic behavior were also checked. NumPy documentation was checked for fixed-string indirect stable sorting, counts and immutable byte buffers. The choice is a small installed alternative rather than another array storage format or a new dependency. Reusing the loader's parser would not provide independent numeric conversion evidence. A new Parquet copy would add storage without resolving source interpretation by itself.

The role boundary is consistent with Arp et al. (2022), §2.2 and Table 8, retrieved in the owner's RAG as chunks 8, 9 and 57. Those passages identify preprocessing and feature selection on final-test data as data snooping. This audit is an explicitly permitted inspection of the stored **development** candidate, including its three roles, for engineering integrity. Its ranges must not be reused as a fitted scaler, a feature-selection result or a classifier-tuning allowance. Actual reserved sources remain outside access. Validation selection is allowed only by a separate explicit declaration; calibration is not a model-selection role.

## Prespecified sample and independent parser

`audit_candidate_independently.py plan` reads only the already sealed metadata and pinned controls. Before opening feature-array values or source CSV rows, it exclusively writes the plan containing each permitted source, its hash, row count, output offset and selected zero-based source rows. The deterministic rule includes:

- the first and last parsed data rows of each of the 14 sources;
- both sides of every internal source-write chunk boundary;
- both sides of every global output-array chunk boundary within that source;
- seven SHA-256 draws per source using the declared fixed string seed and source path, reduced modulo its row count and deduplicated with the other selections.

This sample is not chosen by label, feature value or model outcome. Colliding draws remain one sampled row with its recorded reasons. The exact plan hash is required for the audit. The code recomputes the metadata-only specification and requires equality, including its executed source/commit context.

The audit opens only exact permitted Normal/DDoS development paths through the unchanged guarded source opener. It reuses that access guard and the control pins, not the numeric parser, key function or role assignment as an independent result. Every source is hashed on the same open descriptor before and after its C-parser pass; fingerprints must also match. These checks reduce accidental mutation risk. They are not an absolute defense against a malicious writer that changes and restores bytes between checks.

The C parser reads the ordered 73 predictor fields as float64 with its round-trip converter and the timestamp as text. It rejects nonfinite values and requires the independent row count. Each selected source-row identity addresses the sealed output by its declared source offset, with independent checks of stored source ID and source row. All 73 float64 **bits**, including signed zero, and the stripped ASCII timestamp must match. No failing value is repaired. The results record counts, source-row identifiers/digests and source hashes, without writing sampled feature values or raw tokens.

An exact sampled match is not an independent reparse of every stored feature row. The full source pass establishes the C parser's row count and finiteness, while the value-to-output comparison remains sampled. A failure leaves `FAILED.json` and the partial phase receipts and never writes `COMPLETE.json`. New output directories and new plan files are required; no completed evidence is replaced.

## Full ranges, integer risk and multiplicity

`feature_ranges` streams all sealed rows. It records finite float64 minima/maxima, hexadecimal representations of those endpoints, exact counts of integral/nonintegral stored values, the largest absolute stored integral value as a Python integer, zeros and negative zeros. The threshold for investigating original integer tokens is **at or above** 2^53, so a token such as 2^53+1 that rounded down to 2^53 is not missed. This is an exact-representation boundary, not a scientific feature cutoff.

If any stored integral value reaches that boundary, a separate bounded C-parser string pass inspects that feature's original decimal tokens across all 14 permitted sources. `Decimal` tests original token integrality and exact representability by its converted float64. A detected integer loss is an explicit audit finding, without changing the source or arrays. Decimal tokens themselves are not written. No flagged candidates means that no additional token pass is needed. Stored integrality does not establish that a feature physically represents an integer count or verify its units.

`multiplicities` sorts only the stored key digests and visits every source row. For each stored unordered endpoint-pair/protocol key, it counts rows and native observers, requires one original global role, and compares complete 73-field vectors. Equality uses full finite float64 vector bytes with signed zeros canonicalized to the same numeric zero in a temporary comparison buffer. It is not inferred solely from a numeric-vector hash. Per-key dictionaries are discarded between keys. The audit writes a per-key table, a per-key/observer table and aggregate multiplicity histograms. It reports both within-observer identical pairs and cross-observer identical pairs, as well as keys and key/observer cells with feature variation.

Stored-key equality, exact numeric-vector equality and physical episode identity are distinct. This code neither deduplicates records nor treats their copies as independent episodes. The training unit and any weights remain a parent-reviewed choice. Credible choices include a declared source-row baseline, an explicitly stored-key-balanced sensitivity, or weights for exact numeric copies within a key while preserving all ownership. The latter two change the statistical unit and require their own information/aggregation accounting; neither becomes physical episode weighting by renaming it.

## Read-only purpose interface

`PurposeDataset(directory, expected_features=..., candidate_sha256=..., assignment_sha256=...)` opens through the loader's complete seal, checks the exact ordered feature and label/role schema, and streams all metadata to verify source-row addressing, native owner 1..10 and known global roles. Observer zero, unknown roles and malformed schemas fail. It exposes these named views:

| View | Rows and labels available | Required declaration |
|---|---|---|
| `supervised_train(owner)` | That observer's training predictors, binary labels and whitelisted identities | Training purpose is fixed by the method name. |
| `unlabeled_train(owner)` | That observer's training predictors and whitelisted identities; no labels argument or label reads | Training purpose is fixed. |
| `trusted_benign_anchor(owner, identities, approval_id=...)` | Explicitly selected benign training rows of one native observer, returned without labels | Outside-detector benign approval and exact source-row identities. Role/owner checks precede benign-label reads. |
| `unlabeled_train(owner, exclude_anchor=anchor_view)` | All that observer's training rows except its explicitly approved anchor, in original stored order | Only an anchor from the same dataset and owner is accepted. The anchor remains counted as training evidence once. |
| `validation_selection(owner, declaration_id=...)` | Validation predictors and labels for an explicitly declared model-selection allowance | Nonempty selection declaration. Calibration cannot be substituted. |
| `scoring(role, owner, declaration_id=..., frozen_scorer_id=...)` | Validation or calibration predictors and identities, without labels in each batch | Declared post-freeze purpose and scorer digest. `reporting_labels` is separate and checks those exact role/owner/row identities. |

Training view methods take no caller-selected role. Every view keeps final partial batches. Worker identities contain only source ID, source row, observer ID, role ID and key digest; labels and timestamps are absent. New batch arrays use immutable byte buffers, so callers cannot re-enable writes. Source mappings remain read-only. A synthetic bridge checks these batches against the unchanged AF-BKM interfaces, with declared anchor exclusion and all remaining tails consumed.

This is a guard for trusted research code. Private Python attributes, process memory, direct `np.load` or forged declarations can bypass it. It is not a malicious-code enclave, source authentication, or a guarantee that a caller's frozen-scorer assertion is truthful. It provides a narrow, reviewable interface and explicit access declarations. No actual validation model selection or held-out scoring is performed by opening these views.

## Running the checks

Use the locked environment and set the existing research workspace root as usual. The plan and audit commands require the same contract/registry pins used by the completed loader:

```sh
python scripts/audit_candidate_independently.py plan --prepared reports/development-preparation/PREPARED --contract reports/CONTRACT.json --registry reports/REGISTRY.json --contract-sha256 CONTRACT_SHA --registry-sha256 REGISTRY_SHA --plan reports/development-preparation/AUDIT-PLAN.json
python scripts/audit_candidate_independently.py run --prepared reports/development-preparation/PREPARED --contract reports/CONTRACT.json --registry reports/REGISTRY.json --contract-sha256 CONTRACT_SHA --registry-sha256 REGISTRY_SHA --plan reports/development-preparation/AUDIT-PLAN.json --plan-sha256 PLAN_SHA --output reports/development-preparation/NEW-AUDIT-RUN
```

The full locked unit suite includes fabricated first/last/boundary samples, a high-precision decimal/timestamp check, 2^53+1 token loss, exact source-row addressing, key/observer duplicates and signed-zero equality, seal/schema failures, observer/role leakage, forbidden worker-label reads, declared validation selection, frozen scoring guards, immutable arrays and an AF-BKM bridge. Run the engineering self-test, stock synthetic workflow and AF synthetic workflow as well. Commit the exact checked code before an actual audit. Keep the actual plan, controls, source hashes, execution receipt, phase times, hardware/thread disclosure, RSS, output hashes and all failed runs private.

The next neural/statistical workload remains a separately reviewed development comparison. It needs a frozen training unit, eligible benign anchor, per-arm preprocessing/information rules, a source-row schedule, parameter and selection allowances, stopping/resource budgets, charged message contents and a post-freeze held-out reporting procedure. An audit pass establishes none of the raw-capture or laboratory conditions required for controlled sampling/timeouts, live metering compatibility or deployment timing claims.
