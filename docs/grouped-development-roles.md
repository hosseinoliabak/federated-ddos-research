# Grouped development-role candidate, version 1

This preparation step gives the FLNET development records reproducible training,
validation and calibration roles. It produces an inspectable candidate before
model training. It does not freeze a scientific evaluation protocol or open the
reserved test sources.

The training records are available for fitting model parameters. The validation
records are held aside for the declared development comparisons and model
selection. A separate calibration role reserves records for choosing a decision
threshold under a later, explicit calibration rule. This script assigns the
roles and counts their support. It does not fit a model, select a threshold or
establish that the calibration sample is sufficient. Cross-validation is not
implemented by this script.

## Assignment and source identities

The input proposal records development source paths, their SHA-256 hashes,
original labels and observer IDs. This version accepts only the documented FLNET
Normal and DDoS directories. It preserves D1–D10 as source observer identities.
Using these observers as logical clients is an experimental choice; the script
does not establish real provider PoPs or customers.

`flow_metadata.connection_key` preserves the stored address, port and protocol
strings, after trimming whitespace. It sorts the two address-port pairs so that
reversed endpoints produce the same key. It does not include the observer,
label or timestamp. `prepare_grouped_roles.assign_role` hashes this key with an
explicit seed and version, then assigns it according to the declared positive
integer role weights. A key therefore has the same role wherever it appears.
The weights describe allocation probabilities over keys; actual record
proportions can differ because keys have different numbers of observations.

This grouping does not identify independent sessions or captures. For example,
reused endpoint pairs remain grouped across dates. Related attacks with different
keys can still appear in different roles. The hash allocation also mixes dates,
so it does not test performance on future traffic. These limits must constrain
the interpretation of any later experiment.

FLNET2023 describes ten router observation nodes in its emulated GEANT topology
(Kumar et al., 2023, Section III-A, printed page 346). Arp et al. (2022, discussion
of data snooping and Appendix Table 8) explain how development choices made using
test data contaminate the final evaluation. These sources support preserving
source identities and reserving test data. They do not prescribe the role weights,
prove independence of these keys or validate this experimental candidate.

## Run on a private workspace

Use the locked project environment and set `FDDOS_WORKSPACE` to the private data
workspace. The example below is a candidate configuration, not an accepted ratio
for every dataset.

```json
{
  "version": "flnet-grouped-role-candidate-v1",
  "candidate_id": "flnet-role-candidate-01",
  "dataset": "flnet2023",
  "claim_scope": "within_release_grouped_holdout",
  "group_definition": "stored_unordered_address_port_pair_and_protocol_v1",
  "role_seed": "flnet-role-candidate-01",
  "role_weights": {"train": 8, "validation": 1, "calibration": 1},
  "minimum_rows_per_client_role": 1
}
```

Save the policy as `config/flnet-role-policy.json` in that workspace, then run
from the code checkout.

```sh
uv run --frozen python scripts/prepare_grouped_roles.py \
  --policy config/flnet-role-policy.json \
  --output reports/development-preparation/flnet-role-candidate-01
```

The source proposal defaults to `config/split-proposal.json`. Paths must remain
inside the workspace. Reserved entries are skipped before opening or hashing
their files. Development entries pointing into TEST, including symlink targets,
are rejected. The script hashes each development source before parsing and
checks its size, modification time and inode afterward. These checks detect the
specified changes; they are not an adversarial integrity guarantee.

CSV rows must still be parsed to select their metadata columns. Predictor strings
are not converted to numbers, summarized or used for fitting. Original source
files are not written. Dataset tables, identifiers and digests remain private;
hashing stored addresses is not a privacy guarantee.

## Inspect the candidate

The output contains counts by client, role, original label and stored date,
shared-key counts between observer pairs, and counts by stored destination digest.
A stored destination is not a customer group. The manifest also records source
hashes, the assignment digest, policy and code hashes, Git context, dependency
lock, timing and peak process memory. Its elapsed boundary excludes final
serialization; source hashing and parsing/accounting times are recorded
separately.

`support_checks.binary_class_counts` makes absent attack classes visible for each
observer and role. A passed total-row minimum does not imply that recall is
defined or that calibration is reliable. Inspect these counts and the date and
label associations before accepting a training experiment. No accepted source
or client scope should be inferred from this program merely completing.

`COMPLETE.json` means only that candidate preparation completed. A failed run
keeps `FAILED.json`; neither outcome may overwrite an existing output directory.
The recorded assignment digest covers source path, row ordinal, client, key,
role and original label in sorted source-path order. Reproduction requires the
same verified sources, code and policy. Different row ordering changes this
provenance digest even when key roles remain unchanged.

## Checks

The regression tests use synthetic metadata to check shared keys across clients
and labels, direction symmetry, invalid policies, source identity and hash
validation, missing metadata, source preservation, reserved-source exclusion,
support warnings and overwrite refusal. The synthetic integration workflow also
poisons reserved CSV contents before running this preparation. These checks test
program behavior; they do not establish suitability of the real datasets.
