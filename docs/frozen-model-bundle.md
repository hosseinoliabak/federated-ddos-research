# CSV frozen scorer and transform recovery

This candidate exports a self-contained score-only snapshot from a completed
five-arm engineering run. It reuses the checked weight codec, scaler math,
MLP constructor, AF state validators and purpose views. Worker and coordinator recovery are separate interfaces. It does not establish
physical feature semantics, customer identity, independent episodes, deployment
readiness or a useful operational FPR.

`frozen_model_bundle.py` provides five small interfaces:

1. `CompletedRun(directory, complete_sha256)` verifies the pinned completion seal
   and all recorded run artifacts. Dataset/reserved directories are rejected
   before artifact access; this API has no raw-source/test-path argument.
2. `recover_train_transforms(dataset, completed, output, owner=...)` requests only that owner's named
   `PurposeDataset.unlabeled_train(owner)` views. It reproduces each owner's
   original256-row moment blocks, including every
   tail. Counts, candidate/assignment/prepared-array pins and recorded mean/M2
   digests must match exactly. The sealed result stores mean, M2 and denominator
   values, identities/order digests, extra reads, UTC/monotonic timing and RSS.
   The view must belong to the requested owner and dataset. Predictor and
   identity counts must agree, and source-row pairs must be unique within the
   owner's pass. The resulting native-order identity digest and count must match the
   existing `source_access_passes` entry for `independent_local/unlabeled_train`.
   Missing or ambiguous entries fail recovery. This uses the run's recorded
   field rather than adding a retrospective identity record. Agreement of this
   declared identity sequence and aggregate moments does not independently
   prove that each predictor row is paired with its recorded identity.
   `merge_train_transforms(completed, messages, output)` accepts only existing
   validated count/mean/M2 frames from all10owners and merges them in native-owner
   order. The coordinator has no dataset/view argument or raw-predictor input;
   recipients receive only mean/denominator frames. Summary/fanout application
   bytes are recorded separately; no transport timing is claimed.
   A zero TRAIN variance has denominator1; an untrained client is not silently
   exported as a trained model. Failure receipts and partial counts remain.
3. `export_bundle(...)` copies the checked neural frame and actual transform
   values, or the complete AFv2 final state. Local models retain local ownership;
   pooled/FedAvg models use the final global frame. A FedAvg client frame is a
   preaggregation update and is not exported as the final global model.
4. `load_bundle(directory, expected_bundle_id)` validates the complete file
   allowlist, byte/hash/schema/owner/state/runtime bindings and reconstructs a
   read-only `FrozenScorer`. Loading or scoring needs no source run or dataset.
   Provenance must retain a null customer map and the family's separate-recovery
   cost flag. Independent-local, pooled and FedAvg transform counts equal their
   model training counts. A local-shared-moments model has a local model count
   and a global transform count, so that equality does not apply to it. Its
   loader does not independently verify the global TRAIN count. Export binds
   that count to the completed run; a pinned original bundle ID rejects resealed
   changes without reopening that run.
5. `FrozenScorer.score(...)` accepts only finite float64 predictor arrays and the
   exact feature/input-contract/client declaration. `score_view(...)` requires a
   matching unlabeled validation/calibration scoring view. It returns scores and
   identities without reading labels. Streaming receipts distinguish completed,
   failed and unfinished output; invalid input never becomes a benign score.

The neural path preserves float64 standardization followed by float32 forward
computation and sigmoid. It uses evaluation and inference modes and restores CPU
RNG state after reconstructing the model. The tests compare a NumPy reference
and hand-computable logits with rtol2e-6/atol2e-7, then require exact equality with
the same locked Torch inference path. AF decoding preserves the final round and
fixed covariance; it does not reset a final state to satisfy the round0 decoder.
A final AF state must have a round of at least 1, even when a caller supplies an
internally consistent round0 state and matching IDs.

External decisions use a separately exported `reporting-thresholds.json` pinned
to the scorer/input IDs. The artifact declares calibration role, source and
membership hashes, benign support, an exact rational-alpha order-statistic rank,
and actual finite thresholds. `decide(...)` applies **score > threshold**,
including ties and sigmoid endpoints. Missing scope/support, wrong scorer or
invalid values raise explicit failures. No calibration fitting function is
included. A trusted caller supplies the declared calibration artifact; the API
is not an enclave that proves how that declaration was obtained.
The policy schema and application helper do not verify calibration membership,
recompute a benign order statistic, or authenticate the origin/owner of a bare
score array. Those are caller assertions. Empirical decisions remain unused
until a separately checked calibration pipeline verifies sealed membership,
threshold derivation and identity-linked score ownership. Score-only validation
does not call this helper. Accepting a declaration is not evidence that an actual
completed score-only run selected or used that threshold.

`csv_schema(...)` records exact ordered names and an embedded unverified stored
CSV semantic/metering contract. Source-registry and full-input hashes are
separate from the names-only schema hash. This version rejects live eligibility,
physical-unit substitution and other feature widths. No smaller lab feature set
is padded into73inputs. Customer attachment/routing maps remain separate from
native observer/client IDs.

Run the fabricated-only check with the locked Python:

```text
python scripts/check_frozen_model_bundle.py
python -m unittest discover -s tests -p test_frozen_model_bundle.py -v
```

Neither command takes an acquired-data path. The disposable fixture includes
reserved poison files that the inherited preparer/loader excludes before access.
The inherited modules, MIT notice, dependency lock and historical entrypoints
are unchanged. Actual transform recovery, export, scoring and calibration remain
unrun for this implementation milestone. Recovery/export costs are additional
operations and cannot be added retrospectively to the original cost-pilot time.

Hashes detect artifact changes, not an unknown publisher's authenticity.
Path/symlink checks constrain trusted artifact handling; no absolute TOCTOU or
formal privacy guarantee is claimed. The strict candidate decoder targets the
current locked runtime rather than silently promising cross-version inference.
The accepted artifact format remains `frozen-csv-bundle-v1`, with exact NumPy and
Torch version checks and the stricter semantic checks above. The recorded
`bundle_code.source_sha256` identifies the exporter source. It need not equal a
later compatible loader's source. A reproducible consumer can call
`load_bundle(..., expected_export_source_sha256=...)` with the exporter hash from
an independently pinned export execution binding. This optional pin rejects a
different exporter declaration by comparing the caller's expected hash with the
recorded hash, without requiring the exporter to equal the runtime file. It does
not discover or independently establish the expected exporter. A future actual
controller binding must obtain that value from independently pinned export
execution evidence; copying it from the bundle proves no additional provenance.
The complete bundle ID still pins every recorded byte. New controller receipts
must record the current runtime module file hash separately.
Neither hash authenticates an unknown issuer, and matching dependency versions
alone does not prove compatibility of an arbitrary loader change. The fabricated
legacy-load regressions cover this candidate's stated format and changes only.

Evidence: Arp et al.2022 P3/Table8 supports separate fitting/selection roles;
AF-BKM §§4.1–4.4 defines fixed-anchor covariance, label-free worker summaries and
anchor updates. Context7 PyTorch2.13 `load_state_dict`, `eval`, `inference_mode`,
`random.fork_rng` and sigmoid documentation supports the library calls. Source
and API retrieval records remain in the private evidence packet.

Owner-local recovery is sufficient for an independent-local bundle; it never
requests another owner's predictors. The shared transform is reconstructed from
explicit summaries. This also recovers the numerically identical pooled scaler
for export, without relabeling the original pooled training raw-data path. The
implementation is a single-process reference, not a privacy/distribution proof.
