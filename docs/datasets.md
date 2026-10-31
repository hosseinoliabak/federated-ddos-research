# Dataset setup

The first pipeline supports the DDoS/Normal development subset of FLNET2023 and the downloaded CICDDoS2019 CSV archives. Obtain them from the [FLNET repository](https://github.com/nsol-nmsu/FML-Network) and the [CICDDoS2019 publisher](https://www.unb.ca/cic/datasets/ddos-2019.html). Access and redistribution terms belong to those sources. No authenticated download service or browser credentials are part of this code.

## Directory structure

Create this structure beneath `FDDOS_WORKSPACE` after downloading and extracting the source files.

```text
datasets/
  flnet2023/extracted/
    DDoS/
      Dataset-1-BOT.csv
      Dataset-5-STOMP.csv
      Dataset-9-DYN.csv
      Dataset-10-TCP.csv
    Normal/
      Dataset-1.csv ... Dataset-10.csv
    TEST/
      publisher test CSVs
  cicddos2019/extracted/
    01-12/
      publisher development CSVs
    03-11/
      publisher test CSVs
```

Do not rename a file merely to make it fit. Verify its source folder and client meaning first. The FLNET training check requires the four named DDoS files and ten Normal files. The audit and proposal programs currently expect both dataset directories. They are not generic arbitrary-CSV loaders.

Run `inventory_csvs.py` to hash these existing files. Its inventory uses `registered_existing_csv`, which explicitly does not claim a ZIP CRC check. Hashing reserved files for inventory is an integrity operation; their content is not used for fitting or tuning.

## Optional verified ZIP extraction

The original extractor accepts an `acquisition.json` under each dataset directory. Record the archive SHA-256 independently when it is acquired. A FLNET entry has this shape.

```json
{"folders": [{"name": "DDoS", "archive": "raw/ddos-csv.zip", "sha256": "REPLACE_WITH_VERIFIED_SHA256"}]}
```

Use separate entries for DDoS, Normal, and TEST. The FLNET ZIP members must begin with `CSV/`. A CICDDoS2019 manifest uses `archives` entries with `filename` and `sha256`; its ZIP members must retain their `01-12/` or `03-11/` paths. The extractor verifies hashes and CRCs, rejects path traversal and symbolic-link members, and retains a 40 GiB free-space reserve. It refuses to replace existing CSVs or inventories.

This route is an alternative to registering manually extracted CSVs. Run `extract_datasets.py` instead of `inventory_csvs.py`, then continue with the audit. A failed or interrupted extraction may leave completed members and a partial inventory state. Inspect that state and use a fresh destination for a retry; do not delete original archives to force completion.

## Data boundaries

Files under FLNET `TEST/` and CICDDoS2019 `03-11/` are reserved. The audit inspects their headers only. The final test protocol remains unresolved, and the engineering check does not assign a replacement test set. Unknown development labels require review rather than automatic mapping to Normal.

CSV row counts are not counts of independent observations. The group diagnostic uses stored endpoints and protocol values, with no claim that they identify independent transport sessions. Interpret field units and collection dates using source provenance before making a temporal or deployment claim.
