# Engineering method and limits

The current run is a software feasibility check. It is separate from a statistical pilot and a confirmatory comparison. Its purpose is to exercise data preparation, client updates, aggregation, and recorded outputs under a small workload.

## Preparation

The program verifies the 14 FLNET development hashes against the inventory. An unordered address-port endpoint pair and the stored protocol value define a candidate connection key. Client ID, label, and timestamp do not enter that identity. Domain-separated SHA-256 calculations select approximately one group in 64 and assign approximately one fifth of selected groups to validation. The assignment is global, so an observed connection cannot receive different roles at two clients.

The program checks that no candidate group or identical full stored record appears in both roles. This check does not rule out dependence between groups from the same capture. The split is not a final estimate of generalization to new organizations or future traffic.

Original labels are retained with a separate binary mapping. Source-client membership and class skew are preserved. No blanket deduplication or rebalancing is applied. Addresses, ports, protocol, timestamp, and label are excluded from predictors. Three minimum inter-arrival-time fields are excluded provisionally pending interpretation of negative values. Other numeric columns form the input interface, so synthetic fixtures can use a smaller interface than the real files.

Standardization is fitted on pooled fitting rows only and applied unchanged to validation. Constant fitting columns use scale one. The pooled fit is an engineering reference, not a privacy-preserving or distributed preprocessing protocol. The final study must choose and justify its preprocessing design.

## Training

The detector has one 16-unit ReLU hidden layer and one output logit. Its unweighted binary cross-entropy objective is trained for three rounds. All ten clients participate, with one local epoch and batches of 256. Each round starts clients from the same global model and weights their returned parameters by local fitting counts.

The fixed SGD learning rate is 0.01 with no momentum. Local Adam uses 0.001, beta values 0.9 and 0.999, and epsilon 1e-8. Both have zero weight decay. Local optimizer state is reset every round. These settings are not tuned, so this run cannot rank the optimizers. Local Adam is not server-side FedAdam.

The seed is fixed. Initial model weights and minibatch schedules are matched between methods. Sequential CPU execution uses two PyTorch threads. Float32 local models are aggregated using float64 intermediate arithmetic and then converted back to the parameter dtype. No distributed network latency is measured.

Validation logs include loss, confusion counts, recall, false-positive rate, and average precision at a fixed probability threshold of 0.5 where applicable. Average precision uses scores rather than the thresholded predictions. Recall and average precision are left undefined for clients without attack support. The fixed threshold is an engineering choice; it has not been selected for an operational false-positive target.

## Reproduction and resources

Record the Git commit, dependency lock, source inventory, configuration, seed, backend, and full execution logs. `COMPLETE.json` hashes the saved artifacts. The working source scripts used before this public repository are identified by hashes in `import-provenance.json`. Portability edits form a new code version and must not be cited as the exact source of an earlier run.

The full audit reads CSVs in chunks but retains row fingerprints, and the exact overlap confirmation retains complete unique records in memory. Therefore, neither is constant-memory processing. The initial audit uses three worker processes. The original development workload was run on a 64 GB machine; smaller machines should use the synthetic example first and review capacity before full processing. The exact-overlap tool is bounded to less than 3 GiB of FLNET input bytes, which does not imply a 3 GiB RAM limit.

The synthetic example tests execution and invariants only. Its intentionally simple features, labels, and dates cannot support a detection-performance claim. Test results on it must never be reported as benchmark results.

## Remaining decisions

The final study still needs verified field meanings, capture provenance, an evaluation claim, the final split, feature policy, tuning budget, quality target, practical effect margins, replication count, and timing/failure analysis. The QiML implementation specification also remains unresolved. These decisions must precede confirmatory test evaluation.
