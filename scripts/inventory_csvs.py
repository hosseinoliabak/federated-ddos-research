"""Register already extracted CSV files without changing their contents."""

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
from research_workspace import workspace_root, contained_path

PATTERNS = {
    "flnet2023": ("DDoS/*.csv", "Normal/*.csv", "TEST/*.csv"),
    "cicddos2019": ("01-12/*.csv", "03-11/*.csv"),
}


def main():
    root = workspace_root()
    for dataset, patterns in PATTERNS.items():
        base = root / "datasets" / dataset
        manifest = base / "extraction.json"
        if manifest.exists():
            raise FileExistsError(f"Existing inventory preserved: {manifest}")
        entries = []
        for pattern in patterns:
            for candidate in sorted((base / "extracted").glob(pattern)):
                path = contained_path(root, candidate.relative_to(root))
                with path.open("rb") as stream:
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
                entries.append(
                    dict(
                        dataset=dataset,
                        path=str(path.relative_to(root)),
                        bytes=path.stat().st_size,
                        sha256=digest,
                        status="registered_existing_csv",
                        archive_crc_verified=False,
                    )
                )
        if not entries:
            raise FileNotFoundError(f"No recognized CSV files for {dataset}")
        base.mkdir(parents=True, exist_ok=True)
        with manifest.open("x") as stream:
            json.dump(entries, stream, indent=2)
        print(
            json.dumps(
                dict(
                    dataset=dataset,
                    files=len(entries),
                    checked_at_utc=datetime.now(timezone.utc).isoformat(),
                )
            )
        )


if __name__ == "__main__":
    main()
