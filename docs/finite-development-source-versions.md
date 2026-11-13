# Finite development source versions

The finite runner keeps local and collective fitting, validation selection, and
serialized application-message accounting explicit. Its command-line example
uses constructed data. It does not run the acquired-data study or a final test.

## Executed source and current integration

The four private development stages used commit
[`3c3679dd96adcd788c8b4bac144bb12c7aea61f9`](https://github.com/hosseinoliabak/federated-ddos-research/tree/3c3679dd96adcd788c8b4bac144bb12c7aea61f9).
That commit is the source reference for those procedures. A proposed immutable
`finite-development-v4-20261113` tag makes the commit reachable without replacing
the newer public branch. Source identity does not establish that a procedure or
its data are scientifically valid.

This integration adds the same finite/scalar modules and their tests to the
published `025cd41` tree. Their bytes are unchanged. The newer bundle validation
and raw-reference files are retained. One module in the finite import closure,
`frozen_model_bundle.py`, differs from the executed tree. Its later validation
checks remain in place. The finite scorer already requires a positive final AF
round, so the newer helper checks the same condition again.

The [source correspondence](finite-development-source-correspondence.json)
records the five unchanged code/test files and all 14 local import modules.
It distinguishes module-byte identity from the numerical comparisons made on
constructed fixtures. The integrated tree is not the exact original runtime
closure and no acquired-data rerun is attributed to it.

For exact source inspection, check out the full executed commit. For the newer
public validation and raw-reference tools, use the integrated branch. Keep the
dependency lock and record the commit used for any new run. Private controllers,
datasets, model files and manuscript material are not distributed here.

## Procedures and checks

`finite_development.OptimizerSpec` records the SGD/Adam settings.
`run_finite_development.Plan` records the supported horizons and budgets.
`run_finite_development.prepare` stages TRAIN views and builds own or shared
moments. `finite_development.choose` selects from complete arm-specific records,
using each local owner's mean validation BCE or the collective union criterion
over the declared seeds. These mechanisms do not define a calibrated reporting
threshold or establish convergence.

The AF-family schedule uses a designated reference ridge and neighboring
sensitivity values. It does not choose a winning ridge from attack-label
results. The scalar diagnostic selects its field and orientation from TRAIN
data, then reports separate fixed-validation measures.

Run the commands from a clean checkout with its locked environment. Choose a
new output directory for the finite example.

```sh
uv run python -m unittest discover -s tests -v
uv run python scripts/engineering_pilot.py --self-test
uv run python scripts/check_demo.py
uv run python scripts/train_separability_diagnostic.py --synthetic
uv run python scripts/run_finite_development.py --synthetic --output /tmp/fddos-finite-v4-new-run
```

These commands use invented records and states. They check software behavior,
including ownership/role restrictions, continuation, tails, missing scores,
selection and message accounting. They do not establish acquired-data accuracy,
independent observations, customer identities, population false-positive rates
or router readiness. The older finite procedure notes are retained as historical
pre-execution records rather than descriptions of this integration's execution.

The local integration checks considered 398 unit cases. They executed 397 and
skipped one optional private TShark case. The engineering self-test, synthetic
workflow, frozen-bundle check, scalar example and finite example passed. A
separate cross-tree fixture comparison matched 194 scorer/logit output records,
the two selection records and three stage-count/application-byte summaries.
It covered both supported neural layouts, SGD and Adam, and two AF ridge values.
These are fabricated checks, not a repeat of the acquired-data experiment.

The packet-layer probe also passed using the already cached Scapy 2.5.0 source.
Its first `uv --offline` invocation could not initialize the sandboxed cache;
that observation did not establish a missing package. No dependency was
installed or upgraded. The research workflow runs the unit checks and both new command-line examples for pushes and pull requests.

Training, validation and final evaluation must retain their declared roles.
Arp et al. (2022, Section 2.2) discuss how preprocessing can compromise that
separation. That methodological warning does not verify this implementation.

## Reference

Arp, D., Quiring, E., Pendlebury, F., Warnecke, A., Pierazzi, F., Wressnegger, C.,
Cavallaro, L., & Rieck, K. (2022). Dos and don’ts of machine learning in computer
security. In *Proceedings of the 31st USENIX Security Symposium* (pp. 3971–3988).
[Publisher paper](https://www.usenix.org/conference/usenixsecurity22/presentation/arp)
