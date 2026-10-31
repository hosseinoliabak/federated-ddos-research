"""Extract verified research CSV archives without modifying their originals."""

from pathlib import Path, PurePosixPath
import hashlib, json, shutil, stat, zipfile
from research_workspace import workspace_root, contained_path

ROOT = workspace_root()


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main():
    results = []
    for dataset in ("flnet2023", "cicddos2019"):
        base = ROOT / "datasets" / dataset
        if (base / "extraction.json").exists():
            raise FileExistsError("Existing extraction inventory preserved")
        manifest = json.loads((base / "acquisition.json").read_text())
        entries = manifest.get("folders", manifest.get("archives", []))
        for item in entries:
            archive = contained_path(
                base, item["archive"] if "archive" in item else "raw/" + item["filename"]
            )
            assert digest(archive) == item["sha256"], f"Archive hash mismatch: {archive.name}"
            prefix = Path(item["name"]) if dataset == "flnet2023" else Path()
            if dataset == "flnet2023" and item["name"] not in ["DDoS", "Normal", "TEST"]:
                raise ValueError("Unsupported FLNET folder")
            with zipfile.ZipFile(archive) as z:
                infos = z.infolist()
                assert len(infos) < 2000
                needed = sum(i.file_size for i in infos if not i.is_dir())
                assert shutil.disk_usage(base).free > needed + 40 * 1024**3, (
                    "Insufficient free space"
                )
                for info in infos:
                    part = PurePosixPath(info.filename)
                    assert (
                        not part.is_absolute()
                        and ".." not in part.parts
                        and "\\" not in info.filename
                    )
                    assert not stat.S_ISLNK(info.external_attr >> 16)
                    if info.is_dir():
                        continue
                    if part.suffix.lower() != ".csv":
                        results.append(
                            {
                                "dataset": dataset,
                                "archive": archive.name,
                                "member": info.filename,
                                "status": "excluded_non_csv",
                                "bytes": info.file_size,
                            }
                        )
                        continue
                    if dataset == "flnet2023" and (len(part.parts) < 2 or part.parts[0] != "CSV"):
                        raise ValueError("Expected a CSV/ archive member prefix")
                    relative = (
                        prefix / Path(*part.parts[1:])
                        if dataset == "flnet2023"
                        else Path(*part.parts)
                    )
                    dest = contained_path(base / "extracted", relative)
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    assert not dest.is_symlink()
                    if dest.exists():
                        raise RuntimeError(f"Refusing to overwrite existing file: {dest}")
                    temp = dest.with_suffix(".csv.partial")
                    h = hashlib.sha256()
                    n = 0
                    try:
                        with z.open(info) as src, temp.open("xb") as out:
                            for b in iter(lambda: src.read(8 * 1024 * 1024), b""):
                                n += len(b)
                                assert n <= info.file_size
                                out.write(b)
                                h.update(b)
                        assert n == info.file_size
                        temp.rename(dest)
                    except BaseException:
                        temp.unlink(missing_ok=True)
                        raise
                    results.append(
                        {
                            "dataset": dataset,
                            "archive": archive.name,
                            "member": info.filename,
                            "path": str(dest.relative_to(ROOT)),
                            "bytes": n,
                            "sha256": h.hexdigest(),
                            "status": "extracted_crc_passed",
                        }
                    )
                    print(
                        json.dumps({"extracted": str(dest.relative_to(ROOT)), "bytes": n}),
                        flush=True,
                    )
        (base / "extraction.json").write_text(
            json.dumps([r for r in results if r["dataset"] == dataset], indent=2) + "\n"
        )
    print("Extraction complete", flush=True)


if __name__ == "__main__":
    main()
