# Federated DDoS research

Research software for inspecting network-flow datasets, preparing a bounded development
subset, checking federated training, and verifying selected mathematical statements.
This project supports Hossein Oliabak's master's research on DDoS detection shared among
organizations or service-provider customers.

The current Python implementation runs SGD and local Adam with a fixed FedAvg server. It
is an engineering prototype. A Sellier-based QiML training engine has not been
implemented, and the project does not establish a speedup, a final detection result, or
readiness for a provider network.

## Project status

A [provider architecture assessment](docs/provider-observation-and-learning.md)
considers provider-owned PoP collection and scoring with central coordination,
Internet-border observations and complementary customer-facing PE views. It
keeps local-only, permitted pooled-central and federated training as choices to
compare on matched inputs. The design is provisional. The comparison is unrun,
with no lab rebuild, new training or selected final protocol.

The [dated project status](docs/project-status.md) records the current evidence,
remaining research gates, and publication boundaries. The [Research
hub](https://oliabak.com/research/federated-ddos/) provides the continuing project
index. The [critical literature review workflow](docs/critical-literature-review.md)
records reading scope, evidence limits, close precedents, and checks on proposed
research gaps.

The nine-chapter English working draft retains four research questions with distinct
roles. Its opening and foundations now establish DDoS and the relevant learning concepts
before the study detail. Required source-data checks, the final learner and protocol,
and the novelty assessment remain open. Chapter 1 awaits human review. No new training
run, numerical QiML engine or final detection result is part of this milestone.

The checked private English draft has nine chapters, 162 PDF pages and 105 bibliography
entries; Chapter 3 cites 67 works. The retained reading bank contains 95 works. The
working Zotero collection has 98 parent references because it also includes three
supporting engineering and measurement records. The public bibliography is a separate
selection of 20 entries. Eight new scholarly sources received targeted reading for
specific explanations. These targeted readings do not establish a fresh full-text
appraisal of all 95 works, an exhaustive systematic review or independent replication.
The earlier collection-year chart remains a historical snapshot of 87 records. Counts do
not establish research completion.

The [foundational reference selection](docs/foundational-reference-selection.md) records
source roles, primary links and reading boundaries. Separate Antigravity and xAI
source-selection critiques returned no blocking findings. Antigravity explicitly
selected Claude Opus 4.6 Thinking without an exposed serving identifier; xAI reported
grok-4.7-build. Their input contained public-source summaries and explanatory
requirements, not revised chapters or full papers. A Grok output-format retry is
recorded; model agreement does not certify novelty or validity. The completed selection
critiques do not approve the manuscript or establish scientific validity. Historical
scientific code remains unchanged.

The [figure and table workflow](docs/figure-workflow.md) describes the reusable
production and validation route without publishing private draft content or assets. This
documentation update leaves the reviewed pilot code unchanged.

The [research-assistance and validation
workflow](docs/research-assistance-and-validation.md) records proportionate disclosure,
separate model critiques, and the different roles of formal, numerical, software,
empirical, and human checks. Planned reviews remain separate from completed ones. This
documentation adds no new proof or experiment.

The [browser LaTeX authoring assessment](docs/latex-authoring-options.md) compares
own-domain editors for chapter files, rendered PDFs, comments and tracked edits.
Ayakaleaf Pro is the leading open-source candidate for a bounded synthetic trial. Source
inspection and local TeXlyre review/recovery checks retain their recorded limits. The
current private workspace remains active; no replacement deployment or manuscript
migration is claimed.

## Current components

| Component | Purpose | Status |
|---|---|---|
| CSV inventory and extraction | Preserve source files and record SHA-256 hashes | Available |
| Development audit | Inspect labels, numeric values, dates, and duplicate candidates | Available |
| Exact overlap checks | Compare repeated FLNET records without deleting them | Available |
| Connection grouping | Coordinate fitting and validation roles between source clients | Available; capture independence remains unresolved |
| Feature-validity diagnostic | Profile development features and fit bounded one-feature checks | Available; exploratory only |
| Training check | Run a small feedforward detector with local SGD or Adam and model averaging | Available; one seed and three rounds |
| Portable engineering bundles | Preserve model inputs and weights for offline transfer | Available; destination validation pending |
| Lean verification | Check three aggregation lemmas and five scoped algebra/recording statements | Available; see the formal project |
| QiML training and controlled network lab | Evaluate the proposed treatment and deployment conditions | Planned |

## Install

Python 3.13 and [uv](https://docs.astral.sh/uv/) are required. The dependency lock
covers macOS and Linux. Linux uses PyTorch's CPU package index. The first installation
may download Python and the locked packages.

```sh
git clone https://github.com/hosseinoliabak/federated-ddos-research.git
cd federated-ddos-research
uv sync --locked
```

The scientific dependencies are pinned in `pyproject.toml`, and their resolved
dependencies are in `uv.lock`. Keep the lockfile when reproducing a run. The Lean
environment is separate and has its own toolchain and dependency manifest.

## Run without downloading datasets

The integration check creates small synthetic CSV fixtures in a temporary directory,
runs the pipeline, checks its outputs, and removes only those fixtures afterward. These
records are software-test inputs, not traffic measurements or evidence for the thesis.

```sh
uv run python -m unittest discover -s tests -v
uv run python scripts/engineering_pilot.py --self-test
uv run python scripts/check_demo.py
```

The checks cover unequal client weighting, grouping, numeric audit behavior,
training-only scaling, source preservation, absent-class metrics, reserved-test
exclusion, and refusal to overwrite an existing run. The test workflow also runs on
GitHub Actions. Passing software checks does not validate a scientific hypothesis.

## Work with real data

Keep data in a separate directory and point the tools to it. If `FDDOS_WORKSPACE` is
unset, the default is the ignored `.workspace/` directory inside this checkout.

```sh
export FDDOS_WORKSPACE="$HOME/research-data/federated-ddos"
```

Acquire datasets from their publishers under the applicable terms. Place the CSV files
in the structure documented in [dataset setup](docs/datasets.md). Then run the following
commands from the code checkout.

```sh
uv run python scripts/inventory_csvs.py
uv run python scripts/audit_datasets.py
uv run python scripts/confirm_flnet_duplicates.py
uv run python scripts/confirm_flnet_overlap.py
uv run python scripts/propose_dataset_split.py
uv run python scripts/inspect_flnet_groups.py
uv run python scripts/render_audit_report.py
uv run python scripts/engineering_pilot.py
uv run python scripts/audit_feature_validity.py
```

The inventory command is for CSVs that are already extracted. An optional ZIP extraction
route is documented separately. Do not run both routes against the same existing
inventory. The initial audit uses three worker processes and may consume substantial
memory on the full CICDDoS2019 development collection. Read the [method and resource
limits](docs/methodology.md) before running it.

The pipeline keeps original labels and source-client membership. The test directories
are excluded from model development. The audit may read test headers; the training
program reads only the allowlisted FLNET development paths. Source files are not
rewritten, and completed audits and runs are preserved rather than silently overwritten.

## Read outputs

| Workspace path | Contents |
|---|---|
| `datasets/<dataset>/extraction.json` | File identity, provenance status, size, and hash |
| `reports/dataset-audit/audit.json` | Field diagnostics and execution environment |
| `reports/dataset-audit/index.html` | Readable audit report |
| `config/split-proposal.json` | Proposed source roles and unresolved evaluation decisions |
| `reports/development-preparation/flnet-connection-groups.json` | Candidate-group diagnostic |
| `reports/development-preparation/feature-validity-v1/` | Field profiles, descriptive checks, and one-feature diagnostics |
| `runs/engineering-smoke-v1-portable/` | Prepared subset, scaler, logs, checkpoints, and completion hashes |

The candidate connection grouping controls a particular form of overlap. It does not
establish independent captures, attack campaigns, or validity on future traffic. The
selected feature policy and pooled training-only scaler are provisional engineering
choices. See [methodology](docs/methodology.md) before interpreting any reported metric.

The [feature-validity procedure](docs/feature-validity.md) explains the diagnostic
scope, interpretation, and reproducibility record.

The [portable-model guide](docs/portable-models.md) describes the offline bundle
exporter, input contract, network-lab integration, and historical packet-layer
regression.

## Benign-only engineering pilot

The [benign-only pilot](docs/benign-engineering-pilot.md) checks local fitting, FedAvg,
separate target calibration, and later development probes on the frozen historical FLNET
sample. It includes calibrated and fixed packet-count controls. This is a software check
with an arbitrary 5% calibration target. Date/label, target/family, shared-traffic, and
feature-provenance limits prevent interpreting its metrics as independent-source or
operational performance.

Run the required repository checks first. The script requires an explicit
`--execute-development-pilot` flag and writes to a fresh versioned directory under
`FDDOS_WORKSPACE`. See the protocol for data roles, the use of future probe identities
in exclusion, comparator differences, and execution provenance.

## Extend the project

Keep model training, client participation, server aggregation, and evaluation decisions
explicit. A new local optimizer should use the same agreed model and protocol before a
performance comparison is interpreted. Record changes in a new run configuration and
preserve the earlier evidence. The current script is intentionally a bounded reference;
it is not yet a general optimizer plug-in framework.

The next work is to verify source-data feasibility, complete human review of Chapter 1,
and freeze the bounded evaluation protocol. The optional Sellier-inspired branch still
requires a numerical specification. Any live-lab measurements require separate
functional checks; a constructed topology does not establish capture or detector
readiness. The [contribution guide](CONTRIBUTING.md) describes how to add code, tests,
documentation, and evidence together.

## Citation and license

Use the repository's `CITATION.cff` metadata and identify the commit or tagged version
used in your work. No software DOI or completed thesis publication is claimed. Method
and dataset sources are listed in [references](docs/references.md).

Original code and documentation in this repository are licensed under [MIT](LICENSE).
Dataset, paper, and dependency licenses remain separate. This repository does not
redistribute the datasets, article PDFs, unpublished thesis chapters, credentials,
private correspondence, or trained model files.

AI tools assisted with code and documentation. Execution records and human review remain
necessary. AI review is not evidence that an experiment or mathematical correspondence
is correct.