# Scoped mathematical checks

This project contains eight Lean theorems. Three concern normalized aggregation weights. Five concern pointwise complex algebra and a running-minimum record associated with the analysis of Sellier's published method. The training engine is not formalized by these statements.

The source mapping identifies the paper equations, transcription assumptions, and scope. One theorem tests equivalence of a literal transcription of printed equation (9) with the complex equation under specified values. This is a pointwise algebra statement. It is not a PDE solution, a verification of the author's code, or a refutation of the complete training algorithm. Author clarification and the intended numerical implementation remain unresolved.

## Reproduce

Install [elan and Lean](https://lean-lang.org/install/), then work in this directory. `lean-toolchain` selects Lean 4.35.0. `lakefile.toml` pins mathlib, and `lake-manifest.json` pins its dependencies.

```sh
lake exe cache get Mathlib.Algebra.BigOperators.Field Mathlib.Basic.Real.Basic Mathlib.Basic.Complex.Basic Mathlib.Order.Monotone.Basic Mathlib.Tactic.Linarith Mathlib.Tactic.NormNum
python3 check_proofs.py
```

Keep the lockfile rather than updating dependencies during reproduction. The first invocation may download the pinned toolchain and dependency sources. Downloaded code and build files remain under ignored `.lake/` paths.

The check script builds the project, treats warnings as errors, audits all theorem dependencies, and writes versions and hashes to the ignored `verification.json`. Accepted standard axioms are `propext`, `Classical.choice`, and `Quot.sound`. An additional dependency, including `sorryAx`, fails the audit. New proof modules must be registered before the audit can pass.

These exact-real statements do not establish floating-point implementation correctness, PDE existence, FDTD stability, global convergence, privacy, detection quality, or a speedup. Match the source equation and its assumptions to the formal statement before citing it as checked.
