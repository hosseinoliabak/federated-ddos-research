"""Run the complete pipeline on disposable synthetic fixtures, never real captures."""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tempfile

SCRIPTS = Path(__file__).resolve().parent


def invoke(script, env, *args, succeeds=True):
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / script), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if succeeds != (result.returncode == 0):
        raise RuntimeError(result.stdout + result.stderr)
    return result


def main():
    with tempfile.TemporaryDirectory(prefix="fddos-demo-") as temp:
        root = Path(temp) / "workspace"
        env = os.environ.copy()
        env["FDDOS_WORKSPACE"] = str(root)
        invoke("make_demo_workspace.py", env, str(root))
        originals = {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*.csv")
        }
        for script in [
            "inventory_csvs.py",
            "audit_datasets.py",
            "confirm_flnet_duplicates.py",
            "confirm_flnet_overlap.py",
            "propose_dataset_split.py",
            "inspect_flnet_groups.py",
            "render_audit_report.py",
        ]:
            invoke(script, env)
        # Poison held-out content after its permitted header-only audit. Preparation
        # and training must succeed without trying to parse or profile those records.
        for p in [
            root / "datasets/flnet2023/extracted/TEST/reserved.csv",
            root / "datasets/cicddos2019/extracted/03-11/reserved.csv",
        ]:
            p.write_text("this is deliberately not a valid model input\n")
        invoke("engineering_pilot.py", env)
        run = root / "runs/engineering-smoke-v1-portable"
        prepared = json.loads((run / "preparation.json").read_text())
        trained = json.loads((run / "training.json").read_text())
        assert prepared["cross_role_groups"] == 0
        assert prepared["cross_role_identical_full_records"] == 0
        assert prepared["all_ten_clients_in_both_roles"]
        assert prepared["validation_perturbation_scaler_check"] == "passed"
        assert trained["matched_initialization"] and trained["matched_batch_orders"]
        assert set(trained["runs"]) == {"sgd", "adam"}
        for method in trained["runs"].values():
            assert len(method["rounds"]) == 4
            for client in ["2", "3", "4", "6", "7", "8"]:
                assert method["rounds"][-1]["validation"]["clients"][client]["recall"] is None
        for relative, digest in originals.items():
            if "/TEST/" in relative or "/03-11/" in relative:
                continue
            assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == digest
        # A second run must refuse to replace the existing evidence.
        before = hashlib.sha256((run / "COMPLETE.json").read_bytes()).hexdigest()
        invoke("engineering_pilot.py", env, succeeds=False)
        assert hashlib.sha256((run / "COMPLETE.json").read_bytes()).hexdigest() == before
        print(
            json.dumps(
                dict(
                    status="passed",
                    fixture="synthetic_only",
                    selected_rows=prepared["selected_rows"],
                    clients=10,
                    methods=["sgd", "adam"],
                    checks=[
                        "global group separation",
                        "training-only scaling",
                        "matched initialization and batches",
                        "absent-class metrics",
                        "reserved test exclusion",
                        "source preservation",
                        "overwrite refusal",
                    ],
                )
            )
        )


if __name__ == "__main__":
    main()
