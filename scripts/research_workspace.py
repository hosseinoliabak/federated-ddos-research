"""Resolve the private data workspace separately from the public code checkout."""

from pathlib import Path
import os

if not __debug__:
    raise RuntimeError("Run without python -O; this research prototype uses checked assertions.")


def workspace_root():
    configured = os.environ.get("FDDOS_WORKSPACE")
    return (
        Path(configured).expanduser().resolve()
        if configured
        else Path(__file__).resolve().parents[1] / ".workspace"
    )


def contained_path(root, relative):
    """Reject absolute paths, traversal, and symlinks that leave the workspace."""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in str(relative):
        raise ValueError("Use a relative path inside the research workspace")
    candidate = (root / path).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError("Path leaves the research workspace")
    return candidate
