# Finite development controller v2

This version implements a finite development search on the existing native-client
TRAIN and VALIDATION roles. The earlier one-pass cost runner, frozen bundles,
scalar diagnostic and completed runs remain separate. A passing fabricated run
establishes software behavior only. No larger acquired-data search is reported here.

The purpose of the search is to compare bounded optimization choices while keeping
information access explicit. Each independent local selector receives only its own
client's validation records. The pooled and FedAvg selectors receive the permitted
validation-union objective. For these collective objectives, clients compute stable
BCE from frozen logits and send identity-bound loss-sum/count messages. These
validation summaries are charged as collaboration. The pooled trainer separately
receives a reconstructed raw TRAIN cache; local and FedAvg trainers never receive
that cache. All methods remain a trusted, single-process simulation.

`scripts/finite_development.py` defines immutable predictor-only scorers, a new
architecture-aware parameter codec, JSON optimizer-state archives, budget counters,
and the selectors. `scripts/run_finite_development.py` defines the finite schedule,
source-bound preparation cache, continuous training trials, failure receipts and
the AF sensitivity fits. No public acquired-data CLI or arbitrary-role API is added.

The fixed16 stage uses SGD rates .001, .01 and .1 and Adam rates .0001, .001 and
.01, with seeds 20261112 and 20261113. Each arm/configuration/seed has one continuous
four-presentation trial with checkpoints after complete presentations 1, 2 and 4.
Each presentation retains every TRAIN row and partial final batch. Initialization
is paired across arms. Each native owner's fixed seeded permutation repeats at
each presentation; pooled training visits owner blocks 1 to 10. This ordering is
not chronological or a globally shuffled raw union.

Local and pooled optimizers retain their state throughout each continuous trial.
FedAvg uses every native owner each round and weights the returned parameters by
native TRAIN row counts. Its client Adam state starts empty each round; no server
Adam is used. This Adam variant is not FedAdam and does not reproduce the original
SGD FedAvg unchanged. Archived model/optimizer/transform states can reproduce the
next presentation on fabricated inputs, but automatic resume is deliberately
absent. An actual resume would need a new finite protocol amendment.

Selections minimize the mean BCE over the two seeds. A candidate requires both
complete horizon trials and all required owner records; missing or failed slots
remain in the record and do not receive fabricated losses. Exact ties prefer the
earlier checkpoint, then the listed grid order. The wider 64/128/64 capacity stage
uses SGD .01 alone. The shared-moment local ablation is a separate collaboration
condition. Neither stage automatically expands the grid or selects a common
true-local architecture using shared validation feedback.

Ranking continues to use sigmoid float32 scores. Float32 logits are separately
bound to the checkpoint and used for stable BCE, with a float64 reduction for the
selection objective. These representations are explicitly distinct. Constant
scores and endpoint ties retain their valid AUC/AP when both classes occur.
Tie/endpoint fields are descriptive diagnostics and do not change metric
eligibility. Single-class validation has NA ranking but retains its BCE and exact
score coverage. No classification threshold, calibration, confusion matrix or
final-test operation is performed.

The AF stage prespecifies a 2,000-row trusted Normal TRAIN anchor from owner 1 by
the lowest SHA-256 identity keys, with source-row tie-breaking. Anchor selection
never ranks predictor values or observed outcomes. Only the selected exact IDs are
excluded from workers; all other benign and attack rows and every tail remain.
Workers receive no labels. Ridge .001 remains the source-reference candidate;
.0001 and .01 are sensitivity values, each with two seeds. All six fits and their
fixed-validation rank reports remain visible; there is no best-of-six label-based
selection. The inherited AF no-accepted-worker merge advances the protocol round
without rescoring the anchor. Actual anchor visits are summed from merge receipts;
round-count times 2,000 is an upper bound, not a guaranteed measurement.

The source paper's 2,000 baseline count is adapted to stored CSV rows here, whose
physical packet interpretation is unverified. Native ownership, global data roles,
identity hashing, 256-row blocks, full traversal and the strict numerical rules are
study adaptations. The former full-anchor model is a different completed fit.

The proposed stage time ceilings are 10,800, 5,400, 1,800 and 5,400 seconds for
fixed16, wider capacity, shared-moment local and AF sensitivity, respectively.
They are scheduling controls, with no operational or power claim. Parameter and
summary messages have separate limits from pooled raw movement. Cold cache reads,
raw serialization and moment exchange are charged once within each stage;
per-trial marginal times exclude that shared preparation. Checks occur at batch,
message, round, checkpoint and terminal boundaries. Storage is refreshed from
actual files at checkpoints; retained failure receipts can exceed a ceiling.
The private outer controller also records startup, input seal/source hashing and
terminal-seal verification, and imposes the stage deadline on a fresh child.

A failed or capped trial retains counters, completed checkpoints, partial model
and optimizer state, missing-score counts for the whole trial universe, and the
unstarted slots. A partial score is never relabeled benign. An incomplete stage
does not receive a successful COMPLETE seal. Failed trials consume their original
slots; they are not retried or removed after seeing their result. Checkpoint 4
selection records the tested horizon boundary and does not demonstrate convergence.

The strict artifact-path and reserved-source guards are retained. Linux and Darwin
RSS units are handled explicitly in the new version; an unknown platform fails the
measurement rather than silently assigning units. Actual results from the original
Mac controllers remain unchanged.

Run only fabricated inputs from the public CLI:

```sh
uv run python scripts/run_finite_development.py --synthetic --output /tmp/fddos-finite-new-run
```

The output path must be new. The targeted unit suite adds exact continuation,
original one-round SGD equivalence, architecture/scorer integrity, isolated
selection, full participation/tails, failure-universe and exact-anchor checks.

Source note: Arp et al. (2022), RAG chunk 11, supports separate validation for
selection; Li et al. (2020), RAG chunk 8, describes local SGD and averaged client
updates; Kairouz et al. (2021), RAG chunk 39, distinguishes adaptive variants.
The AF RAG query did not retrieve the target paper. Its official Section 5 and
Table 3 were therefore checked directly at https://doi.org/10.3390/iot7030067.
The PyTorch 2.13 optimizer/state and stable BCE APIs and scikit-learn 1.9.0 rank
metric documentation were retrieved using Context7. The finite grid, caps,
selection channels and identity rule are study decisions, not universal rules
established by these sources.
