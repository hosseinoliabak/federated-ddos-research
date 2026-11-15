"""Build the thesis lemmas and audit the transitive axioms of every checked theorem."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone

root = Path(__file__).resolve().parent
env = os.environ.copy()
env["PATH"] = str(Path.home() / ".elan/bin") + os.pathsep + env.get("PATH", "")

def run(*args):
    result = subprocess.run(args, cwd=root, env=env, text=True, capture_output=True)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    result.check_returncode()
    return result.stdout

modules = {
    "ThesisVerification/Aggregation.lean": "ThesisVerification",
    "ThesisVerification/Sellier.lean": "ThesisVerification.Sellier",
    "ThesisVerification/Foundations.lean": "ThesisVerification.Foundations",
    "ThesisVerification/Sampling.lean": "ThesisVerification.Sampling",
    "ThesisVerification/SamplingFlow.lean": "ThesisVerification.SamplingFlow",
    "ThesisVerification/ControlledDesign.lean": "ThesisVerification.ControlledDesign",
}
# Fail closed if another Lean module is added without registering its audit.
actual_modules = {str(p.relative_to(root)) for p in (root / "ThesisVerification").rglob("*.lean")}
if actual_modules != set(modules):
    raise SystemExit("Register every proof module in the axiom audit before building")
run("lake", "build")
found = {}
allowed = {"propext", "Classical.choice", "Quot.sound"}
for module, namespace in modules.items():
    audit = run("lake", "env", "lean", "-DwarningAsError=true", module)
    source = (root / module).read_text()
    expected = {namespace + "." + name for name in re.findall(r"(?m)^theorem\s+(\w+)", source)}
    declarations = {}
    for name, text in re.findall(r"'([^']+)' depends on axioms:\s*\[([^]]*)\]", audit):
        declarations[name] = sorted(x.strip() for x in text.split(",") if x.strip())
    # Lean reports an axiom-free theorem with a different sentence; record it as an empty list.
    for name in re.findall(r"'([^']+)' does not depend on any axioms", audit):
        declarations[name] = []
    if not expected or set(declarations) != expected:
        raise SystemExit("Axiom audit did not cover every theorem in " + module)
    for name, axioms in declarations.items():
        if set(axioms) - allowed:
            raise SystemExit("Unapproved axiom dependency in " + name)
    found.update(declarations)
files = ["lean-toolchain", "lakefile.toml", "lake-manifest.json", "ThesisVerification.lean", *modules, "check_proofs.py", "sellier-source-map.json", "foundations-source-map.json", "sampling-source-map.json", "design-source-map.json"]
report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "lean": run("lean", "--version").strip(),
    "lake": run("lake", "--version").strip(),
    "build": "passed",
    "axioms": found,
    "sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files},
    "scope": "Three normalized-weighting lemmas, five Sellier-specific pointwise algebra and recording checks, and forty Chapter 2 checks (logistic loss and its derivative and convexity, Adam bias correction for a constant input, the federated objective and FedAvg weights, the flow-score maximum, the order-statistic threshold, the violation-bound arithmetic, and two-counter aliasing), and seventeen checks for the RQ2 sampling analysis (the product weight of independent packet selection with its deletion, single-packet and binomial retained-count probabilities, the one-quarter selection threshold, and the recall ceilings for decision rules on keys shared by attack and benign records), and seven checks for the flow-level corollary of that ceiling (a deterministic rule on the maximum per-record score, or on an aggregate between the smallest and the largest per-record score, alerts on no flow or episode whose records all lie on keys that benign traffic carries with mass above the false-positive budget), and 124 checks for propositions P1 to P12 of the controlled-study design v2.1 (unbiasedness and variance of rescaled counts under independent selection, thinning of the negative binomial law with integer size and of the Poisson law, distinct source hosts under selection, the rank-rule threshold and its exchangeable false-positive rate on a finite sample space, the paired alert difference, the design effect of a cluster mean, the covariance of mixed Poisson counts with a shared rate component, the logic of the interval decision rules, standardization under a common scale factor, and the threshold probabilities of NB(5, 40) and NB(5, 10) certified with exact rationals). Exact real-number, finite-combinatorial, and convergent-series statements, with one statement for a general probability measure (the P11 corollary). The probabilistic guarantee of Tong et al. Proposition 1 is not formalized. The sampling checks do not establish that the implemented HMAC-SHA256 selector behaves as independent selection, do not model the flow meter, and use no measured count. The design checks do not formalize the sum of two Gamma variables, the Poisson-Gamma mixture, the Gamma variance, or the negative binomial law with a non-integer size, and they treat the keyed selector as independent selection without proving it. No PDE existence, FDTD stability, implementation, floating-point, global convergence, privacy, detection or runtime claim."
}
(root / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"PASS: {len(found)} theorems built; only the documented standard axioms were found.")
