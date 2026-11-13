# Five-arm cost runner, candidate version1

This runner is ready for synthetic engineering checks. It has not run on actual data. The parent-selected settings describe one complete training presentation for measuring cost; they are not final detection hyperparameters, convergence evidence or an operational FPR requirement. The standalone CLI accepts only `--synthetic`; the callable runner accepts an already verified `PurposeDataset` for a later parent-reviewed execution.

## Reuse and version boundaries

The existing historical entrypoints provide the small 73–16–1 neural architecture and SGD settings, but their data preparation cannot be reused as the matched runner. This new runner uses the checked purpose views. It reuses the reviewed strict AF numerical/state/access machinery without editing its v1 files. A full fork of every numerical component would add duplicate code; an unversioned patch would obscure the reviewed singleton behavior. The chosen small v2 extension and separate v2 wire preserve v1 reproduction and expose the changed invariant. No new dependency was installed. NumPy, PyTorch and the already locked transitive `threadpoolctl` are used directly.

The primary AF method is [Al Saleh and Azar (2026), DOI10.3390/iot7030067](https://www.mdpi.com/2624-831X/7/3/67), §§4.1–4.4/Algorithm1. The publisher HTML §4.4 Eq6 explicitly divides `n/(1+dispersion)`. The source acknowledges unbounded reported means in §§4.2/4.4. The inspected public code is [commit8f6ac0f80bdc8d40ce2bd22227f6544facad0487](https://github.com/josephazar/af-bkm/tree/8f6ac0f80bdc8d40ce2bd22227f6544facad0487); `federated.py` lines70–73 use unscaled distance MAD and omit a singleton candidate. Its MIT notice remains in `licenses/AF-BKM-MIT.txt`. Exact original v1 function lines were checked in the local files, rather than copied from review-generated anchors.

## AF paper-fidelity correction

`afbkm_adapter_v2.py` follows literal Eq5 for any nonempty accepted set. A singleton has dispersion0 and a finite candidate equal to its distance. v1 and the pinned public branch instead omit that candidate. With three two-row workers of scaled mean.5, count2 and candidate.5, plus a singleton of mean1, count1 and candidate.5, the old gate excludes the singleton and produces centroid.5. Literal Eq5/Algorithm1 keeps it and produces **15/28 = .5357142857142857** at blend.5. `check_afbkm_v2.py` executes and records both results.

The v2 state/wire version is `afbkm-candidate-v2-paper-singleton`; old/new singleton payloads are not silently interchangeable. The active gate reports finite-candidate inclusion or exclusion precisely. Empty/no-accepted updates retain their own reasons. No minimum-three-row or positive-MAD condition was introduced: sample covariance still requires at least two approved anchor rows. Constant columns are retained, and worker variation in such a column affects the Mahalanobis distance. No new mean-norm or poisoning gate is added. Unbounded finite means can displace the detector; a singleton mean can disclose its scaled point. These are source/protocol limits, not privacy guarantees.

Discriminating fixtures cover distances `[0,0,0,10]` (MAD0, sample standard deviation5), a non-equidistant three-row positive-MAD anchor, two-row/zero-MAD validity, varying worker values in a constant anchor feature and active singleton/outlier reasons. The retained strict finite/SPD checks still fail explicitly; they do not repair invalid scores to benign.

## Exact method and access contract

| Arm | Training information and transform | Exchange counted |
|---|---|---|
| Independent local MLP | Own supervised training records; own unlabelled-training count/mean/M2; population standardization | None. A shared experimental initialization seed is not a data collaboration message. |
| Permitted pooled MLP | Declared union of numeric training rows, labels and whitelisted identities at the coordinator; union population moments | Every actual raw-training application frame, including identity/label bytes and header. |
| FedAvg MLP | Native supervised training; local count/mean/M2 exchanged for a common transform; all clients, one local pass then count-weighted model merge | Moment uplinks, transform fanout, initial model fanout, local model updates and final model fanout. |
| Corrected AF statistical pipeline | All Normal TRAIN rows at observer1 form the outside-detector approved anchor; workers receive unlabelled TRAIN streams with that anchor excluded by source identity | Initial fixed covariance/scaler distribution separately from later summary/state frames; repeated internal anchor scoring counted. |
| Local MLP plus shared moments | Own supervised training, the same common moments as FedAvg; extra collaboration ablation | Moment uplinks and transform fanout, with no model update exchange. |

The neural learner is Linear73→16, ReLU, Linear16→1, with bias and float32 CPU parameters. BCE-with-logits is averaged over each actual minibatch. The selected source-row unit uses no sample weighting, deduplication or resampling. Actual short batches and unequal optimizer-step counts are recorded. Each neural arm starts from the same parameter bytes. Local/FedAvg/ablation models clone that initial state; the pooled model continues one optimizer across owners. The pooled input order concatenates the same per-owner batches, including each tail, rather than forming different cross-owner minibatches. FedAvg aggregates local float32 states with float64 weighted accumulation, then returns finite float32 parameters.

The numerical transform uses float64 mean and centered M2 blocks and a count/mean/M2 merge. For disjoint blocks A,B with delta=meanB−meanA and n=nA+nB, mean=meanA+delta*nB/n and M2=M2A+M2B+delta²*nA*nB/n. This identity follows by expanding each block's squared deviations around the combined mean. Population variance is M2/n; zero standard deviations use denominator1. Negative/nonfinite moments fail. Pooled and shared paths use the same per-owner block/reduction order and are checked bit-identical. Independent-local receives no global moments. A meaningful large-offset fixture avoids subtracting raw squared sums.

Source features/labels come only from named purpose views; no fitting entrypoint calls `np.load` or accesses prepared `_X/_records`. Each owner stages its approved view, retaining source identities and all rows. This single-process simulation holds logical worker stores; it is not multi-host isolation. A `Store` passed to AF has no labels. Anchor label eligibility is outside the detector and its full label-read allowance is recorded. No validation, calibration, held-out selection or quality evaluation is requested.

## Schedule and messages

The per-owner schedule uses `Generator(PCG64(SeedSequence([20261112, owner])))` on the full original native TRAIN identity sequence. An AF anchor exclusion filters this same permutation by exact source ID/row, preserving the relative sequence. It is not a second reshuffle or capture chronology. Duplicate source identities or missing schedule members fail. Repeated keys and identical numeric copies remain distinct retained records.

AF continues until all streams are exhausted, retaining partial tails. Empty/no-accepted summaries, exhausted workers, kept/rejected gate reasons, counts and round times are retained. Every later state is fanned to all10 configured owners, including exhausted ones; that explicit engineering policy is charged. Numeric parameters remain fixed in an all-empty merge while protocol round identity advances. The scaler/covariance are never updated from workers. Internal anchor threshold recomputation is training; no external reporting calibration occurs.

`workload_messages.py` implements exact length-prefixed canonical-header/binary-array frames with strict key, role, owner, dtype, shape, finite-value and identity checks. Moment/transform fields are float64; model fields are float32; pooled raw frames additionally contain binary labels and fixed identity bytes. Raw frames are forbidden for every other arm. The 2MiB parser bound is an engineering cap. Encode/decode/encode reconstruction is checked for every transferred frame. `messages.jsonl` records logical fields, round, direction, SHA and exact application bytes, without storing raw source rows. These are serialized simulations, not measured network packets, transport overhead or distributed latency. Checksums and scope declarations are not remote authentication.

Neural initialization, final aggregation, model-message admission and moment/transform admission use the expected full identity metadata. Partial forward/backward/optimizer work counters are retained on failure. A missing/invalid update fails the run with a retained receipt and no completion seal. Checkpoints are local artifacts; their sizes are separate from exchanged payloads. No failed or absent quality decision becomes a benign prediction: quality decisions are not requested in this cost-only task.

## Concrete preset and execution evidence

The preset is seed20261112, CPU numerical-thread request2, batch256, SGD lr.01/momentum0/weight-decay0, one complete presentation per neural arm and FedAvg1round×1local pass. AF uses ridge.001, MADk3, blend.5, trustk3 and blocks256; its anchor is all Normal TRAIN rows at observer1. [The JSON preset](matched-cost-pilot-v1.json) records these values explicitly. Test-only smaller batches exercise unequal tails; they do not replace the preset.

The standalone fresh-process CLI sets OpenMP/OpenBLAS/MKL/Accelerate startup caps to2 before importing numerical libraries. The runner also sets PyTorch intra-op threads to2 and uses installed `threadpoolctl` to limit supported detected pools. It records detected limits and startup environment. Accelerate's actual thread count is not exposed by that controller here; OS thread count and energy are not measured. A later actual run must use a fresh process with the same startup caps and disclose the supported-controller limit rather than claim all runtime threads are observed.

```sh
python scripts/check_afbkm_v2.py
python -m unittest discover -s tests -v
python scripts/engineering_pilot.py --self-test
python scripts/check_demo.py
python scripts/check_afbkm_adapter.py
python scripts/run_matched_workload.py --synthetic --output /tmp/NEW-SYNTHETIC-COST-RUN
```

Receipts record source/lock/config/candidate/assignment hashes, UTC/monotonic timing, per-arm/client/round durations, source access and repeated preprocessing rows, optimizer steps, anchor rescoring, serialized bytes and RSS. Dataset-seal opening is caller-timed separately from the runner's boundary. The final source commit and synthetic run evidence must be bound before review. No actual-data model cost, convergence, accuracy, calibration or deployment result is established.

Source note: the AF primary HTML and local PDF pp7–9, exact pinned public code, McMahan et al. (2017) RAG chunks9/10 for local passes/weighted model averaging, and Context7 NumPy/PyTorch2.13/threadpoolctl docs were consulted. RAG did not retrieve the AF primary or the specific moment-merge paper; the checked primary supplied AF evidence, while the displayed moment identity is a stated derivation with hand/large-offset checks. All settings above are accepted engineering-pilot choices, not source-derived universal budgets.
