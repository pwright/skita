from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

MARKER_TO_TYPE: dict[str, Optional[str]] = {
    "CONCEPT": "concept",
    "PROCEDURE": "task",
    "REFERENCE": "reference",
    "ASSEMBLY": None,
}


@dataclass
class TopicSpan:
    topic_id: str
    topic_type: Optional[str]   # 'concept' | 'task' | 'reference' | None (for assembly)
    confidence: str             # 'declared' | 'inferred/high' | ... | 'reviewed'
    heading: str
    heading_depth: int
    source_path: str
    start_line: int
    end_line: int
    role: str                   # 'assembly' | 'topic'
    anchor: Optional[str]       # raw anchor id when present
    intro_lines: list[str] = field(default_factory=list)
    members: list[TopicSpan] = field(default_factory=list)
    content_lines: list[str] = field(default_factory=list)


@dataclass
class Finding:
    finding_id: str
    rule: str
    severity: str               # 'inventory' | 'advisory' | 'blocking'
    topic_id: str
    message: str
    evidence: str
    source_path: str
    start_line: int


@dataclass
class SourceContainer:
    source_path: str
    source_hash: str
    frontmatter: dict
    spans: list[TopicSpan]      # top-level declared spans
    candidates: list[dict]      # unmarked headings (heuristic candidates)


@dataclass
class RunManifest:
    skita_version: str
    source_path: str
    source_hash: str
    run_id: str
    timestamp: str
    span_count: int
    finding_count: int
