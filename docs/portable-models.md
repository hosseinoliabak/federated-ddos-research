# Portable engineering models

The bundle helper moves the existing small feedforward model between Python environments while preserving its input contract. A bundle contains CPU weights, the architecture name and hidden width, ordered feature names, fitting-data scaling parameters, class labels, and the decision threshold. Its manifest records file hashes and the exporter source hash. These hashes detect changes; they do not authenticate an unknown publisher. Load only bundles from a trusted run.

This is an offline engineering interface. It is not a packet extractor, a live detector, or evidence of detection quality on another network. The current FLNET extractor identity remains unverified. Equal column names do not establish equal feature definitions, units, flow direction, or timeout behavior. Establish that correspondence before using a model with newly captured traffic. A replacement extractor may require a new training run.

## Export a completed run

For a new checkout, the example below uses the portable run produced by the current pipeline. It is not a claim that this run is identical to a historical run. Use the exact run ID whose checkpoint and manifest you verified. The private historical transfer check used `engineering-smoke-v1`; selecting a different run requires its own checks.

From the repository root, after setting `FDDOS_WORKSPACE` as described in the README:

```sh
uv run python scripts/engineering_bundle.py --run engineering-smoke-v1-portable --optimizer sgd
uv run python scripts/engineering_bundle.py --run engineering-smoke-v1-portable --optimizer adam
```

Outputs appear under `bundles/<run>-<optimizer>-v1/` in the data workspace. Existing outputs are preserved and cause an error. The exporter checks source-run hashes and retains the original training script hash. Exporting does not retrain the model or attribute a historical run to newer code.

Transfer the complete bundle over your authenticated management connection to a Linux detector node. Install this repository at the intended commit and run `uv sync --locked`. Linux uses the locked CPU PyTorch package. Loading the weights on CPU avoids a dependency on the training machine's GPU. Numerical correspondence must still be checked in the destination environment.

## Use the Python interface

The input must be a finite numeric matrix in the recorded feature order, with 1 to 10,000 rows per call. The caller supplies the feature names explicitly. The helper applies the stored scaler and threshold.

```python
import sys
sys.path.insert(0, "scripts")
from engineering_bundle import load_bundle, predict, select_features

metadata, model = load_bundle("/path/to/trusted/bundle")
# records are named flow-feature dictionaries from your verified extractor.
values = select_features(metadata, records)
probabilities, predictions = predict(metadata, model, values, metadata["features"])
```

`select_features()` explicitly projects named records into the stored order, ignores extra fields, and rejects missing inputs. It does not verify extractor semantics. The historical 73-feature policy excludes six metadata fields and three minimum-IAT fields from the 82 non-label columns; see `engineering_pilot.py`, `META` and `UNCERTAIN`.

The stored threshold is an engineering setting, not operational calibration. The current pooled fitting-only scaler also does not establish private federated preprocessing. Preserve these limitations when reusing the code.

## Network-lab integration

In a network emulator such as EVE-NG, a Linux detector node can receive a configured mirror of traffic. The intended pipeline is capture, verified flow extraction, stored preprocessing, model inference, and timestamped alerts. A normal switch connection alone does not provide a complete traffic copy. Verify capture coverage and loss before interpreting detection results.

Hold inference on lab or replayed traffic until matched PCAP/CSV extraction establishes the selected feature contract, or train a new model under a validated pinned extractor with the evaluation split predefined. Synthetic feature fixtures and original fitting rows can still be used for software transfer checks. An offline capture pilot should precede a live adapter. Features defined over a completed flow become available only when that flow is closed or timed out. Earlier decisions require a separately specified prefix or window representation and corresponding training. Keep monitoring traffic separate from the management connection used to transfer bundles.

The exporter and loader are implemented in `scripts/engineering_bundle.py`. Unit tests cover an independently calculated small example, feature-order and numeric checks, altered weights, altered source runs, and overwrite refusal. The synthetic integration workflow exports both optimizer models. These checks do not establish performance or validity on captured traffic.

## Historical packet-layer regression

```sh
uv run --script scripts/probe_packet_layers.py
```

This isolated script pins Scapy 2.5.0 to reproduce historical field lookup on four fabricated packets. It compares unqualified protocol/flag access with explicit IP/TCP layer access. It neither sends packets nor reads a dataset. The old dependency is used only for these offline fixtures, not as a recommended live capture stack. It is separate from the research environment's dependency lock.

The fixture can explain how a parsing mistake arises. It cannot identify the software that produced a particular dataset. Relevant primary sources are [Scapy's layer API](https://scapy.readthedocs.io/en/latest/usage.html), the [historical CICFlowMeter Python implementation](https://github.com/hieulw/cicflowmeter/tree/4ff68b0de316e3213655c1d5e20f99469915a744), [PyTorch model serialization](https://docs.pytorch.org/docs/stable/notes/serialization.html), and [EVE-NG Linux nodes](https://www.eve-ng.net/index.php/documentation/howtos/howto-create-own-linux-host-image/).
