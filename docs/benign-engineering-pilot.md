# Benign-only engineering pilot

This pilot checks whether a local and a federated autoencoder can use distinct
fitting, calibration, and development-probe roles without violating the declared
boundaries. It reuses the historical FLNET engineering sample. Its outputs are
descriptive software diagnostics, not answers to the thesis research questions,
evidence of novelty, or estimates of operational performance.

The input is the unchanged `runs/engineering-smoke-v1/selected-records.parquet`
under `FDDOS_WORKSPACE`, with SHA-256
`e0d3812373cc304448e62aef23f3cf8c5dea2db35faf0b39e183768b310552ea`.
The script checks this fixed digest and the historical preparation manifest,
then validates provenance before decoding predictors. It never opens raw CSVs,
publisher TEST files, or CIC reserved sources. A new run directory is required;
existing runs cannot be overwritten.

## Version and input validation

The current program is `new-source-benign-engineering-v2`. The completed v1
run and its source hashes remain historical evidence; they are not rerun or
attributed to this version. Version 2 adds input validation and complete row
accounting, requires both controls, and records finalization failures. Its
new donor shuffle seeds mean that its numerical trajectory must not be assumed
to reproduce v1.

Both Parquet reads explicitly use PyArrow. Before splitting or constructing a
model, every label must be a nonmissing, nonblank string and the required
`tot_fwd_pkts` control column must exist. Invalid labels cause failure; they are
not silently relabeled. The direct `run_target` API applies the same check.

## Data roles

Targets are the original FLNET router IDs 1, 5, 9, and 10. For each target,
only May 11 Normal observations can supply local fitting and calibration data.
The cutoff divides the ordered distinct stored timestamps approximately in half.
All rows of a candidate group go to fitting when its latest timestamp is at or
before the cutoff, and to calibration when its earliest timestamp follows it.
Groups spanning the cutoff are discarded. The saved provenance and accounting
also retain discarded and unassigned target rows. Counts of rows and distinct
candidate groups are reported by stored date and original label. Unassigned
rows do not become fitting, calibration, or probe observations. Distinct group
counts within roles are not necessarily additive. Empty roles or a failure to establish
strict fit-before-calibration order stop that target.

This ordering assumes that the stored ISO timestamps order the observations.
The physical clocks, independent episode boundaries, and exact release
extractor remain unverified. No row-hash ordering substitutes for timestamps.

Every candidate key observed at the target is removed from the other clients
before their May 11 Normal rows are selected for donor fitting. The key is the
historical unordered address–port endpoint pair plus stored protocol, preserved
from the earlier preparation. **This exclusion uses identities from later target
probes. It is a transductive exclusion guard, not a deployable access protocol.**
It establishes separation of those stored keys, not independence of captures or
unobserved related traffic. Empty donors are recorded and excluded; records are
not reassigned to another source.

The probes remain separate: May 13 DDoS observations and May 17 Normal
observations. These are later than the fitting history but not contemporaneous
with each other. The release's date/label confound remains. Each attack-supported
target also has a different attack family, so source and family effects cannot
be separated by comparing those targets. The other six routers do not supply
an attack-recall comparison in this subset.

## Detector and controls

The provisional numeric interface follows the prior engineering exclusions.
It excludes identifiers, ports, protocol, timestamp, label, and three unresolved
minimum inter-arrival fields. This interface has 73 features in the frozen
sample; it is not a validated physical measurement contract.

Each autoencoder has an input layer of dimension `d`, 16 ReLU hidden units, and
`d` reconstructed outputs. Training minimizes mean squared reconstruction error.
Adam uses learning rate 0.001, betas 0.9/0.999, epsilon `1e-8`, zero weight decay,
and batches of 256. Parameters are float32, while reported reconstruction scores
use float64 arithmetic. Two CPU threads, a fixed seed, and deterministic PyTorch
algorithms are requested.

For each target, the two models begin with identical weights. The local model
fits for three epochs on the local fitting role and carries Adam state between
epochs. FedAvg runs three rounds of one local epoch per retained donor, starts
each donor from the round's broadcast weights, resets Adam state for each donor
in each round, and aggregates by donor fitting-row counts. Sorted retained
donors receive dense ranks. NumPy `SeedSequence` derives each shuffle seed
from the base seed, target, zero-based round, and dense donor rank; the rank
and resulting seed are recorded in the round log.

The federated scaler fits only the retained donor fitting rows. It is an
explicit pooled engineering reference, without a privacy protocol. The local
scaler fits only the target's local fitting rows. **The paired procedures differ
in normalization, sample and update counts, and optimizer-state carry/reset.**
Their descriptive difference cannot isolate a causal effect of federation or
optimizer choice.

Both autoencoders use the same target calibration rows, each with its own
95th-percentile reconstruction threshold. NumPy's `higher` convention selects
an observed order statistic; only a score strictly above the threshold triggers
an alert. The nominal 5% false-positive target is an arbitrary software check,
not a registered operating requirement or a guarantee about later traffic.

Two forward-packet-count diagnostics accompany the autoencoders. The calibrated
score uses the same calibration rows and quantile rule. The historical rule
`tot_fwd_pkts > 2.5` retains its different operating point. Neither diagnostic is
represented as a newly fitted detector. Every metric carries the date/label,
target/family, prior-use, feature-provenance, time-ordering, and episode limits.

## Running and recording

After protocol review and the repository's required checks, run the canonical
script with an explicit execution flag:

```sh
python scripts/benign_pilot.py --workspace "$FDDOS_WORKSPACE" \
  --run-id new-source-benign-engineering-v2 --execute-development-pilot
```

The script saves configuration, feature names, source-role provenance, scalers,
pickle-free model arrays, training progress, per-target metrics, input and
executed-script hashes, Python/package versions, elapsed times, process peak
resident memory, failures, and an artifact manifest. Runtime fields state
whether input validation is included. Memory is a process high-water mark,
not a per-method allocation estimate. Successful and partial training counts
are recorded separately. Completion also requires all expected model/control
metrics. Dependency metadata is collected before target training; a failure
produces a failed run record. JSON artifacts use atomic replacement. If sealing
the artifact manifest fails, the summary is rewritten with failed status while
completed target artifacts are preserved. If the filesystem also prevents the
failure summary from being written, the exception propagates; the execution
wrapper must retain stderr and the nonzero exit status.

The execution record must additionally bind the run to the exact canonical
source and test hashes, `uv.lock` SHA-256, Git base commit, and dirty status.
The parent execution manifest can supply these fields. Historical preparation
retains its original provenance and must not be attributed to a later commit.
Initial input-validation errors fail before a run directory is created, so the
execution wrapper should preserve command output and exit status as well.

Synthetic tests cover unequal-weight FedAvg, scaler isolation, strict group
chronology, target-key exclusion, benign-only fitting, final-path rejection,
quantile/tie behavior, and the complete generated-data path. They do not open
real datasets. The new end-to-end and partial-failure test results must be
checked in the accompanying verification record before real-data execution.

No threshold, feature, donor set, or training budget is adjusted from these
probe outcomes. Unfavorable results do not trigger further performance tuning
on this artifact-prone subset. Engineering defects may still be fixed with new
versioned records. RQ2 history grids, RQ4 composition comparisons, and final
source eligibility require separate protocols.

Source note: the data constraints come from the preserved development audits
and source-eligibility report. Implementation details above were checked against
this versioned script. Required RAG passages from *Practical Research*, chunks
143 and 311, support the feasibility and confounding distinctions; they do not
validate this particular detector or dataset.
