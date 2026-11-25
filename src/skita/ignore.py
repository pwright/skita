"""Load and match .skignore patterns."""
from __future__ import annotations

import fnmatch
from pathlib import Path


def load(source_dir: Path) -> list[str]:
    skignore = source_dir / ".skignore"
    if not skignore.exists():
        return []
    patterns: list[str] = []
    for raw in skignore.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            patterns.append(line.rstrip("/"))
    return patterns


def is_ignored(rel_path: str, patterns: list[str]) -> bool:
    if not patterns:
        return False
    parts = Path(rel_path).parts
    for pattern in patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
    return False
