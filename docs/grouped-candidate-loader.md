# Pinned grouped-candidate loader

`load_grouped_candidate.py` turns one approved FLNET development-role candidate into private, unscaled arrays. It does not choose a split, fit preprocessing, train or score a model, calibrate a threshold, or freeze a scientific protocol. The historical engineering and benign-only entrypoints keep their original purposes.

The loader requires explicit SHA-256 pins for a supplied contract and field registry. The contract binds the source proposal, role policy, candidate manifest and completion seal. Every inventory entry is selected or explicitly excluded; malformed entries fail. Only the fourteen recorded Normal/DDoS paths are permitted. Excluded reserved sources and other datasets are never resolved, statted, opened or hashed. Selected paths must resolve to their exact approved path, and the source descriptor walks directory descriptors with `O_DIRECTORY`/`O_NOFOLLOW` and opens the final file with `O_NOFOLLOW` on supported POSIX systems. This also rejects a parent directory replaced by a symlink between the path check and descriptor traversal. Sealed metadata paths cannot escape by symlink.

A source is hashed before and after parsing using the same open descriptor, with device/inode/size/modification-time checks. The pinned existing connection-key and role functions assign one role globally across observers. Every parsed data-row identity is zero based, excluding the header. The final ordered assignment digest, source and total counts, observer/role/class support, global and per-observer key counts, and shared-key counts must reproduce the candidate. No tail batch is discarded. Any mismatch retains a failed receipt and prevents a completion seal. Existing outputs are never overwritten.

The exact ordered 73 predictors are stored in a C-order, little-endian float64 `features.npy` array. All 76 nonmetadata numeric fields, including the three excluded minimum-IAT fields, must parse as finite float64 values. Finite negative minimum-IAT values remain excluded; the loader does not repair their source semantics. Metadata tokens must be present, labels must match the original mapping, and the timestamp must parse as stored ISO text without timezone conversion. Values are not normalized, clipped or imputed. Float64 storage is a declared numerical representation, not byte-identical CSV text preservation.

`records.npy` uses a fixed-width, nonobject dtype with source ID, zero-based parsed source row, native observer ID, role ID, original label ID, binary label, stored-group SHA-256 and stored timestamp. `schema.json` records all mappings and feature order, and `source-map.json` binds numeric source IDs to the source hashes. Neither observer IDs nor stored-address/group digests establish PoPs, customers, independent episodes or formal privacy.

Separate `.npy` memory maps were chosen over the historical whole-table concatenation and compressed `.npz` route because downstream methods can read bounded slices without materializing all strings or unpacking the whole matrix. Typed Parquet is a credible alternative, but would add another schema/conversion route when the existing numerical consumers use NumPy. This implementation needs no new dependency. The declared array payload is `rows * (73 * 8 + record_itemsize)` bytes, plus headers; this is a shape calculation, not a measured memory peak.

The writer hashes each emitted payload in source-row order, flushes both mappings, reads every saved payload back in bounded slices, and requires matching payload digests before sealing. File hashes also include the `.npy` headers. `open_arrays()` checks the seal and every artifact, then opens numeric arrays with `mmap_mode="r"` and `allow_pickle=False`. It checks exact shapes/dtypes. These hashes detect changes to trusted artifacts; they do not authenticate an unknown publisher.

## Run

Keep controls and runtime artifacts under `FDDOS_WORKSPACE`. Use a new output directory. Supply the exact SHA-256 values from the accepted review record rather than substituting current mutable files.

```sh
export FDDOS_WORKSPACE=/path/to/private/workspace
/path/to/locked/python scripts/load_grouped_candidate.py \
  --contract reports/development-preparation/contract.json \
  --registry reports/development-preparation/registry.json \
  --contract-sha256 <exact-contract-sha256> \
  --registry-sha256 <exact-registry-sha256> \
  --output reports/development-preparation/new-loader-run \
  --chunk-rows 10000
```

`run-state.json` changes from running to completed or failed. A completion seal is written last. Receipts retain code commit/source hashes, lock hash, control pins, input/source accounting, separate hashing/parsing/allocation/flush/readback/artifact-hash times, UTC and monotonic boundaries, CPU/environment/thread scope and peak process RSS. The recorded internal elapsed boundary excludes final receipt writes; an execution wrapper should separately record process wall time including them. Source or output readback/hashing is included only in its named stage. No training time, energy, distributed latency or forwarding behavior is measured.

## Downstream interface and limits

`schema, X, records = open_arrays(directory)` returns immutable mappings. Iterate bounded contiguous ranges of `records`, select `role_id` and `observer_id` locally, and gather only the matching rows of `X`. This permits independent local, pooled and federated consumers to declare their information access. An AF-BKM adapter will additionally select its trusted anchor from train-role Normal observations and consume only native train streams. It must keep updates out of validation/calibration/evaluation, retain all partial batches, fail on invalid intermediate values, and count its actual messages and anchor rescoring. No AF-BKM implementation is included here.

Equal supplied records and roles do not establish that the source captures used a common original sampling, timeout or extraction policy. Physical semantics, customer mapping, independent episode support, final evaluation eligibility and the scientific training/calibration protocol remain separate. This loader check is engineering evidence only.

## Verification and sources

The targeted tests use fabricated CSVs and the original metadata-only preparer as a differential oracle. They cover full feature/row/ownership preservation, reversed/shared keys and tails, excluded and symlink-escaped paths, malformed inventory/schema/labels/values, source changes, digest/count failures, immutable arrays, corrupt outputs and overwrite refusal. Required repository unit checks, engineering self-test and synthetic integration remain separate checks; their synthetic model operations do not establish real-data training results.

NumPy 2.4 documentation was retrieved through Context7 for `numpy.lib.format.open_memmap`, structured dtypes, `memmap.flush` and `numpy.load(mmap_mode="r", allow_pickle=False)`. Python3.13 `os.open`/`dir_fd`, `os.fdopen` and descriptor flags were also checked through Context7, and support was observed in the locked interpreter. Relevant methodological evidence reused from the input-contract work is Arp et al. (2022), §2.2/P3 and Table8, on information separation; FLNET2023 §§III-A/III-C describe the data generation/extraction without identifying this loader's physical input semantics. The fixed key/role implementation and supplied candidate, not a generic paper split ratio, determine all roles here.
