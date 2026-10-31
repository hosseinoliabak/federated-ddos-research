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
    if not expected or set(declarations) != expected:
        raise SystemExit("Axiom audit did not cover every theorem in " + module)
    for name, axioms in declarations.items():
        if set(axioms) - allowed:
            raise SystemExit("Unapproved axiom dependency in " + name)
    found.update(declarations)
files = [
    "lean-toolchain",
    "lakefile.toml",
    "lake-manifest.json",
    "ThesisVerification.lean",
    *modules,
    "check_proofs.py",
    "sellier-source-map.json",
]
report = {
    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    "lean": run("lean", "--version").strip(),
    "lake": run("lake", "--version").strip(),
    "build": "passed",
    "axioms": found,
    "sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in files},
    "scope": "Three normalized-weighting lemmas plus five Sellier-specific pointwise algebra and recording checks. No PDE existence, FDTD stability, implementation, global convergence, privacy, detection or runtime claim.",
}
(root / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
print(f"PASS: {len(found)} theorems built; only the documented standard axioms were found.")
