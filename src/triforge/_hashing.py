"""Stable per-project hash."""
from __future__ import annotations

import hashlib
from pathlib import Path


def project_hash(project_path: str | Path) -> str:
    """12-char sha256 of the absolute, normalized project path.

    Stable across runs and platforms. Trailing slashes are stripped so
    ``/x`` and ``/x/`` map to the same hash.
    """
    abs_path = str(Path(project_path).resolve()).rstrip("/").rstrip("\\")
    return hashlib.sha256(abs_path.encode("utf-8")).hexdigest()[:12]
