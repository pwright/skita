"""Parse a Markdown source container into a SourceContainer with TopicSpans."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

import yaml

from .identity import compute_topic_id
from .model import MARKER_TO_TYPE, SourceContainer, TopicSpan

_ANCHOR_RE = re.compile(r'<a\s+id=["\']([^"\']+)["\']')
_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)')
_MARKER_RE = re.compile(r'^<!--\s*(CONCEPT|PROCEDURE|REFERENCE|ASSEMBLY)\s*-->\s*$')
_FM_DELIM = re.compile(r'^---\s*$')


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def _tokenize(lines: list[str]) -> tuple[dict, list[dict]]:
    """Return (frontmatter_dict, tokens).

    Token shapes:
      {'type': 'anchor',  'id': str,   'line': int}
      {'type': 'heading', 'depth': int, 'text': str, 'line': int}
      {'type': 'marker',  'kind': str,  'line': int}
      {'type': 'content', 'text': str,  'line': int}
    """
    frontmatter: dict = {}
    start = 0

    if lines and _FM_DELIM.match(lines[0]):
        j = 1
        fm_lines: list[str] = []
        while j < len(lines) and not _FM_DELIM.match(lines[j]):
            fm_lines.append(lines[j])
            j += 1
        try:
            frontmatter = yaml.safe_load("\n".join(fm_lines)) or {}
        except Exception:
            frontmatter = {}
        start = j + 1

    tokens: list[dict] = []
    for i in range(start, len(lines)):
        line = lines[i]
        line_no = i + 1  # 1-indexed

        # Standalone marker (must check before heading so <!--X--> on its own line wins)
        m = _MARKER_RE.match(line)
        if m:
            tokens.append({"type": "marker", "kind": m.group(1), "line": line_no})
            continue

        # Heading
        m = _HEADING_RE.match(line)
        if m:
            depth = len(m.group(1))
            tokens.append({"type": "heading", "depth": depth, "text": m.group(2).strip(), "line": line_no})
            continue

        # Anchor tag
        m = _ANCHOR_RE.search(line)
        if m:
            tokens.append({"type": "anchor", "id": m.group(1), "line": line_no})
            continue

        # Content (non-blank only)
        if line.strip():
            tokens.append({"type": "content", "text": line, "line": line_no})

    return frontmatter, tokens


# ---------------------------------------------------------------------------
# Span builder
# ---------------------------------------------------------------------------

def _build_spans(
    tokens: list[dict],
    source_path: str,
    start: int = 0,
    end: Optional[int] = None,
) -> tuple[list[TopicSpan], list[dict]]:
    """Recursively build TopicSpans from *tokens[start:end]*.

    Returns (spans, heuristic_candidates).
    """
    if end is None:
        end = len(tokens)

    spans: list[TopicSpan] = []
    candidates: list[dict] = []
    i = start
    pending_anchor: Optional[str] = None
    pending_anchor_line: int = -1

    while i < end:
        tok = tokens[i]

        if tok["type"] == "anchor":
            pending_anchor = tok["id"]
            pending_anchor_line = tok["line"]
            i += 1
            continue

        if tok["type"] == "heading":
            depth = tok["depth"]
            heading_text = tok["text"]
            heading_line = tok["line"]

            # Consume anchor if it immediately precedes this heading (≤3 lines gap)
            anchor: Optional[str] = None
            if pending_anchor and (heading_line - pending_anchor_line) <= 3:
                anchor = pending_anchor
            pending_anchor = None
            pending_anchor_line = -1

            # Look ahead for a marker on the very next token
            has_marker = (
                i + 1 < end
                and tokens[i + 1]["type"] == "marker"
            )

            if has_marker:
                marker_kind = tokens[i + 1]["kind"]
                content_start = i + 2  # skip heading + marker tokens

                # Span ends at the next sibling/parent boundary.
                # Also stop at an anchor that immediately precedes a sibling/parent
                # heading so the anchor is available as pending_anchor for the next span.
                content_end = content_start
                while content_end < end:
                    t = tokens[content_end]
                    if t["type"] == "heading" and t["depth"] <= depth:
                        break
                    if t["type"] == "anchor":
                        nxt = content_end + 1
                        if (
                            nxt < end
                            and tokens[nxt]["type"] == "heading"
                            and tokens[nxt]["depth"] <= depth
                        ):
                            break
                    content_end += 1

                topic_id = compute_topic_id(anchor, heading_text, source_path, heading_line)
                role = "assembly" if marker_kind == "ASSEMBLY" else "topic"
                topic_type = MARKER_TO_TYPE[marker_kind]
                end_line = tokens[content_end - 1]["line"] if content_end > content_start else heading_line

                if role == "assembly":
                    span, child_candidates = _build_assembly_span(
                        tokens, source_path, topic_id, heading_text, depth,
                        heading_line, end_line, anchor, content_start, content_end,
                    )
                    candidates.extend(child_candidates)
                else:
                    content_lines = [
                        t["text"] for t in tokens[content_start:content_end]
                        if t["type"] == "content"
                    ]
                    span = TopicSpan(
                        topic_id=topic_id,
                        topic_type=topic_type,
                        confidence="declared",
                        heading=heading_text,
                        heading_depth=depth,
                        source_path=source_path,
                        start_line=heading_line,
                        end_line=end_line,
                        role="topic",
                        anchor=anchor,
                        content_lines=content_lines,
                    )

                spans.append(span)
                i = content_end

            else:
                # Unmarked heading — heuristic candidate only
                candidates.append({
                    "heading": heading_text,
                    "depth": depth,
                    "line": heading_line,
                    "anchor": anchor,
                })
                i += 1

        else:
            # Non-anchor, non-heading token between spans: reset pending anchor
            if tok["type"] == "content":
                pending_anchor = None
            i += 1

    return spans, candidates


def _build_assembly_span(
    tokens: list[dict],
    source_path: str,
    topic_id: str,
    heading: str,
    depth: int,
    start_line: int,
    end_line: int,
    anchor: Optional[str],
    content_start: int,
    content_end: int,
) -> tuple[TopicSpan, list[dict]]:
    """Build an assembly TopicSpan, separating intro prose from member spans."""

    # Intro = everything before the first member (anchor-preceding-heading, or bare heading).
    # Stop at an anchor that immediately precedes a heading so the anchor is included
    # in the child-span build pass and gets picked up as pending_anchor.
    intro_end = content_start
    while intro_end < content_end:
        t = tokens[intro_end]
        if t["type"] == "heading":
            break
        if t["type"] == "anchor":
            nxt = intro_end + 1
            if nxt < content_end and tokens[nxt]["type"] == "heading":
                break
        intro_end += 1

    intro_lines = [
        t["text"] for t in tokens[content_start:intro_end]
        if t["type"] == "content"
    ]

    # Member spans from the first child heading onward
    member_spans, child_candidates = _build_spans(tokens, source_path, intro_end, content_end)

    span = TopicSpan(
        topic_id=topic_id,
        topic_type=None,
        confidence="declared",
        heading=heading,
        heading_depth=depth,
        source_path=source_path,
        start_line=start_line,
        end_line=end_line,
        role="assembly",
        anchor=anchor,
        intro_lines=intro_lines,
        members=member_spans,
    )
    return span, child_candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_file(path: Path) -> SourceContainer:
    raw = path.read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    lines = raw.decode("utf-8", errors="replace").splitlines()

    frontmatter, tokens = _tokenize(lines)
    spans, candidates = _build_spans(tokens, str(path))

    return SourceContainer(
        source_path=str(path),
        source_hash=source_hash,
        frontmatter=frontmatter,
        spans=spans,
        candidates=candidates,
    )
