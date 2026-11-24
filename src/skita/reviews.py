"""Persistent reviewed-assignment store (reviews.json in sidecar root)."""
from __future__ import annotations

import json
from pathlib import Path

from .model import TopicSpan


def load(sidecar_dir: Path) -> dict[str, dict]:
    path = sidecar_dir / "reviews.json"
    if not path.exists():
        return {}
    with path.open() as f:
        entries: list[dict] = json.load(f)
    return {e["topic_id"]: e for e in entries}


def apply(spans: list[TopicSpan], store: dict[str, dict]) -> None:
    """Apply reviewed assignments to spans in-place (recursive)."""
    for span in spans:
        if span.topic_id in store:
            entry = store[span.topic_id]
            span.topic_type = entry["reviewed_type"]
            span.confidence = "reviewed"
        apply(span.members, store)
