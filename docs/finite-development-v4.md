# Finite development controller v4

This candidate retains the bounded procedure documented in
[finite development v3](finite-development-v3.md). It strengthens the selector's
arm contract, enforces the AF stage's zero raw-message allowance, and writes each
collective scorer archive once. These are engineering corrections to an unrun
acquired-data candidate. Fabricated checks do not establish detection performance
or readiness for an acquired-data release.

`finite_development.choose` requires an explicit expected `arm` in addition to
the owner. Every supplied record must carry the same arm. Mixed arms, a different
single arm, and missing arm metadata are rejected before eligibility is computed.
An empty record set retains its expected arm and has no eligible candidate. The
runner still filters by arm and owner before calling the helper. A fabricated v3
counterexample showed permissive helper behavior, while instrumented v3 runner
calls already supplied homogeneous arm and owner records. It did not demonstrate
cross-arm selection in an ordinary runner execution.

Both collective arms continue to deliver the complete serialized scorer to each
of the ten owners at each checkpoint. All deliveries and loss-sum/count replies
remain charged. Only the identical owner0 scorer file is written once per trial
checkpoint. The AF stage explicitly constructs its inner budget with
`raw_bytes=0`, matching its declared stage policy. Its normal parameter and
summary messages retain their separate budget.

The finite grid, seeds, architecture families, complete TRAIN presentations,
checkpoint horizons, optimizer-state policies, native row weighting, validation
objectives, failure universe, and time/message/storage ceilings are unchanged.
Independent local selection uses the owner's validation BCE. Collective selection
uses the declared union loss-sum/count objective. The source-reference AF ridge
remains .001; .0001 and .01 remain sensitivity values rather than a label-selected
best-of-six search. Anchor identities keep the `finite-development-v2` hash
namespace and exact exclusion semantics. Calibration and test scoring are absent.

`tests/test_finite_development.py` adds fabricated checks for mixed, absent and
unexpected arm metadata; explicit caller binding; one scorer archive with full
recipient delivery; and the actual AF budget's zero raw cap. Existing continuation,
participation, tail, missing-score, scorer-integrity and anchor-identity checks
remain required. The public CLI still accepts fabricated inputs only:

```sh
uv run python scripts/run_finite_development.py --synthetic --output /tmp/fddos-finite-v4-new-run
```

The v3 source, completed historical runs, and frozen initial-review packet are
preserved. A new private controller and exact source/check bindings must be
prepared after both initial reviews are resolved. Root release remains a separate
gate before any acquired-data fitting.

Source note: these amendment claims were checked directly against the frozen v3
source and fabricated reproductions, then against the changed v4 functions. A
focused RAG lookup did not retrieve this private candidate; it supplied no evidence
for the helper or budget implementation. The methodological and library sources
already recorded in the v3 document are unchanged by these corrections.
