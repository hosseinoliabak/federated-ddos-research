# Checked reusable preparation, November 12, 2026

This integration makes the checked preparation and engineering tools available
without publishing datasets, fitted models, private execution receipts or thesis
drafts. It adds no acquired-data experiment and reports no final detector
comparison. The source versions below remain distinct from this later public
integration and from the source hashes recorded by earlier executions.

| Component | Original source version | Scope |
|---|---|---|
| Role-aware candidate loader | `2ff92fac3d1c534f9799ff40923c397779cc80d7` | Reconstruct the declared development roles and retain reserved-source exclusions. |
| Independent loader audit and purpose views | `f4b971dcad56ec4902dedbacd54834adc36deb82` | Check stored values, identities and multiplicity; expose only the declared stage and owner. |
| AF-BKM-family adapter | `be70c2bcaa8ca0b577ff361cc864f11e4cdfd50f` | Implement a disclosed statistics-sharing candidate with strict numerical and message boundaries. |
| Matched engineering runner | `8ef916cd3c2c25bf6f3608d6ac65b5a62e970cc4` | Account for declared source-row work and application messages in a single-process comparison. |
| Offline raw-reference correction | `b9af25cb6b4d09711fa74634d64d9a52fcb9dbfe` | Retain fragment lineage, conservative source-label reconciliation and separate checksum diagnostics. |

The integration preserves these original commits and their code bytes. The
published loader follow-up at
`4c2668afb6dc4007dd34be9f3584a37c0046cf48` is retained. Historical implementation
notes describe the state at their own checkpoints; later publication does not
relabel an earlier execution as a run of this integration.

## Checks and interpretation

The integrated tree passes all 297 locked unit tests, engineering self-test, stock
synthetic workflow, AF adapter and version-2 checks, and the matched synthetic
workflow. These checks use fabricated fixtures. The fragment CLI check requires
the separately supplied pinned TShark executable; its presence is not an
installation requirement for the other Python checks.

```sh
uv run python -m unittest discover -s tests -v
uv run python scripts/engineering_pilot.py --self-test
uv run python scripts/check_demo.py
uv run python scripts/check_afbkm_adapter.py
uv run python scripts/check_afbkm_v2.py
uv run python scripts/run_matched_workload.py --synthetic --output NEW_OUTPUT_DIRECTORY
```

The dependency declarations and lock are unchanged. The existing CI continues
to run the required Python checks. Passing local checks does not establish a
successful hosted CI run or a published deployment.

The raw-data work supports only a narrow offline connection and counter
reference from one inspected capture. It does not establish packet-level attack
onset, independent attack episodes, capture completeness, a common observation
policy or a controlled sampling/timeout benchmark. Historical analyzer settings,
the cause of checksum discrepancies and exact release-member correspondence
remain unresolved. Checksum diagnostics do not silently become a new admission
veto. UDP checksum absence remains distinct from a valid checksum. See the
[fragment and label reconciliation note](raw-fragment-admission.md) and its
versioned policies for the implemented conditions.

The [matched runner](matched-workload-runner.md) and
[independent audit](independent-loader-audit.md) have their own information,
timing and access boundaries. Serialized application bytes are not measured
network traffic or distributed latency. The public integration supplies no
final accuracy ranking, customer-level result, privacy guarantee or live
deployment claim. Reserved final sources remain outside development.

The frozen CSV scorer and transform-recovery bundle remains a separate
provisional candidate. It is not included here, and no completed independent
review consensus is claimed for it. Later development-search work is also
outside this integration. Final protocol selection and functional laboratory
checks remain separate tasks, including the owner's review of the proposed lab
architecture and IP addressing before construction or traffic generation.

## Attribution

The AF-BKM adaptation cites the primary method and pinned reference code in
[its implementation note](afbkm-adapter.md). The retained
[MIT notice](../licenses/AF-BKM-MIT.txt) names all three copyright holders,
Mohammed Al Saleh, Joseph Azar and Rima Shbaro. The paper's license and the
reference code's MIT license remain distinct.
