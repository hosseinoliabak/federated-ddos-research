# Scoped mathematical checks

This project contains 196 Lean theorems in six modules. They check specific mathematical statements used by the thesis. They do not formalize the training engine, the flow meter, the packet selector, or any measurement.

## Modules

| Module | Theorems | Content |
|---|---|---|
| `ThesisVerification/Aggregation.lean` | 3 | Normalized aggregation weights |
| `ThesisVerification/Sellier.lean` | 5 | Pointwise complex algebra and a running-minimum record for the analysis of Sellier’s published method |
| `ThesisVerification/Foundations.lean` | 40 | Equations of the foundations chapter: the sigmoid and the binary cross-entropy loss with its derivative and the convexity of the logistic-regression objective, parameter counts, the SGD step sign and the Adam bias correction for a constant input, the federated objective and the FedAvg weights, the flow score as a maximum of fragment scores, the order-statistic threshold, the arithmetic of its sample-size bound, and two-counter aliasing |
| `ThesisVerification/Sampling.lean` | 17 | Independent packet selection with probability p: deletion and single-packet probabilities, the binomial retained count, the one-quarter selection threshold, and recall ceilings for decision rules on keys that attack and benign records share |
| `ThesisVerification/SamplingFlow.lean` | 7 | The flow-level corollary of that ceiling for rules on the maximum per-record score or on an aggregate between the smallest and largest per-record score |
| `ThesisVerification/ControlledDesign.lean` | 124 | Propositions P1 to P12 of the [controlled-study design v2.1](../docs/controlled-study-v2.1/README.md) |

The source maps identify, for each theorem, the source statement, the assumptions and the scope: `sellier-source-map.json`, `foundations-source-map.json`, `sampling-source-map.json` and `design-source-map.json`. Their `file` fields name documents in the private thesis workspace and record those documents’ hashes. The design propositions are published as `docs/controlled-study-v2.1/PROPOSITIONS-FOR-LEAN.v2.1.md`; the README in that folder explains the one wording change made after the check. The header of `SamplingFlow.lean` names a `SamplingFlow-source-map.json` that does not exist; its seven theorems are described in `sampling-source-map.json` and in the module itself.

## Scope of the Sellier checks

One theorem tests equivalence of a literal transcription of printed equation (9) with the complex equation under specified values. This is a pointwise algebra statement. It is not a PDE solution, a verification of the author’s code, or a refutation of the complete training algorithm. Author clarification and the intended numerical implementation remain unresolved.

## Scope of the sampling and design checks

The sampling checks do not establish that the implemented HMAC-SHA256 selector behaves as independent selection, do not model the flow meter, and use no measured count. The design checks prove P4 for an integer negative-binomial size only and prove P6 (d), P7 (b) and P9 on finite sample spaces. For P10 they prove the covariance identities only; the sum of two Gamma variables, the Poisson–Gamma mixture and the Gamma variance are not formalized. Simulated values and values of e^(−λ) in the design are numerical results, not theorems. The probabilistic guarantee of Tong et al. (Proposition 1), cited by the foundations chapter, is not formalized; only its combinatorial core is checked.

## Reproduce

Install [elan and Lean](https://lean-lang.org/install/), then work in this directory. `lean-toolchain` selects Lean 4.35.0. `lakefile.toml` pins mathlib, and `lake-manifest.json` pins its dependencies.

```sh
lake exe cache get
python3 check_proofs.py
```

Keep the lockfile rather than updating dependencies during reproduction. The first invocation may download the pinned toolchain, dependency sources and prebuilt mathlib files. Downloaded code and build files remain under ignored `.lake/` paths.

The check script builds the project, treats warnings as errors, audits all theorem dependencies, and writes versions and hashes to the ignored `verification.json`. A copy of the latest record is kept in [`docs/lean-verification.json`](../docs/lean-verification.json). Accepted standard axioms are `propext`, `Classical.choice`, and `Quot.sound`. An additional dependency, including `sorryAx`, fails the audit. New proof modules must be registered before the audit can pass.

These exact-real, finite-combinatorial and convergent-series statements do not establish floating-point implementation correctness, PDE existence, FDTD stability, global convergence, privacy, detection quality, runtime cost, or a speedup. Match the source statement and its assumptions to the formal statement before citing it as checked.
