"""Write run artifacts: model.json, findings.json, manifest.json, report.md."""
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from .model import BatchManifest, FileResult, Finding, RunManifest, SourceContainer, TopicSpan


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _span_to_dict(span: TopicSpan) -> dict:
    d = dataclasses.asdict(span)
    # Replace nested dataclass lists with their dicts (asdict handles this recursively)
    return d


def _container_to_dict(container: SourceContainer) -> dict:
    return {
        "source_path": container.source_path,
        "source_hash": container.source_hash,
        "frontmatter": container.frontmatter,
        "spans": [_span_to_dict(s) for s in container.spans],
        "candidates": container.candidates,
    }


def _finding_to_dict(f: Finding) -> dict:
    return dataclasses.asdict(f)


# ---------------------------------------------------------------------------
# report.md builder
# ---------------------------------------------------------------------------

def _span_summary_lines(span: TopicSpan, indent: int = 0) -> list[str]:
    pad = "  " * indent
    type_label = span.role if span.role == "assembly" else span.topic_type or "unknown"
    id_label = f"`{span.topic_id}`"
    conf = span.confidence
    lines = [f"{pad}- **{type_label}** {id_label} — _{span.heading}_ (depth {span.heading_depth}, {conf}, line {span.start_line})"]
    for m in span.members:
        lines.extend(_span_summary_lines(m, indent + 1))
    return lines


def _build_report(container: SourceContainer, findings: list[Finding], manifest: RunManifest) -> str:
    def all_spans(spans):
        result = []
        for s in spans:
            result.append(s)
            result.extend(all_spans(s.members))
        return result

    all_s = all_spans(container.spans)
    assemblies = [s for s in all_s if s.role == "assembly"]
    topics = [s for s in all_s if s.role == "topic"]
    blocking = [f for f in findings if f.severity == "blocking"]
    advisory = [f for f in findings if f.severity == "advisory"]
    inventory = [f for f in findings if f.severity == "inventory"]

    lines: list[str] = [
        "# Skita Scan Report",
        "",
        f"**Source:** `{container.source_path}`  ",
        f"**Run:** `{manifest.run_id}`  ",
        f"**Timestamp:** {manifest.timestamp}  ",
        f"**Hash:** `{container.source_hash[:16]}…`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Declared spans | {len(all_s)} |",
        f"| Assemblies | {len(assemblies)} |",
        f"| Topics | {len(topics)} |",
        f"| Unmarked headings | {len(container.candidates)} |",
        f"| Blocking findings | {len(blocking)} |",
        f"| Advisory findings | {len(advisory)} |",
        f"| Inventory findings | {len(inventory)} |",
        "",
        "## Topic Spans",
        "",
    ]
    for span in container.spans:
        lines.extend(_span_summary_lines(span))
    lines.append("")

    if container.candidates:
        lines += ["## Unmarked Headings (heuristic candidates)", ""]
        for c in container.candidates:
            anchor_note = f" — anchor `{c['anchor']}`" if c["anchor"] else ""
            lines.append(f"- depth {c['depth']}, line {c['line']}: _{c['heading']}_{anchor_note}")
        lines.append("")

    if blocking:
        lines += ["## Blocking Findings", ""]
        for f in blocking:
            lines += [f"### {f.rule} (line {f.start_line})", "", f.message, ""]
            if f.evidence:
                lines += [f"> {f.evidence}", ""]

    if advisory:
        lines += ["## Advisory Findings", ""]
        for f in advisory:
            lines += [f"### {f.rule} — `{f.topic_id}` (line {f.start_line})", "", f.message, ""]
            if f.evidence:
                lines += ["> " + line for line in f.evidence.splitlines()]
                lines.append("")

    if inventory:
        lines += ["## Inventory", ""]
        for f in inventory:
            lines.append(f"- **{f.rule}:** {f.message}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Batch report builder
# ---------------------------------------------------------------------------

def _build_batch_summary(batch: BatchManifest) -> str:
    lines: list[str] = [
        "# Skita Batch Scan Report",
        "",
        f"**Source dir:** `{batch.source_dir}`  ",
        f"**Run:** `{batch.run_id}`  ",
        f"**Timestamp:** {batch.timestamp}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| .md files found | {batch.file_count} |",
        f"| Processed | {batch.processed_count} |",
        f"| Ignored (.skignore) | {batch.ignored_count} |",
        f"| Errors | {batch.error_count} |",
        f"| Total spans | {batch.total_span_count} |",
        f"| Total findings | {batch.total_finding_count} |",
        f"| Blocking | {batch.blocking_count} |",
        f"| Advisory | {batch.advisory_count} |",
        "",
        "## Files",
        "",
        "| File | Spans | Findings | Blocking | Advisory | Status |",
        "|---|---|---|---|---|---|",
    ]

    for fr in batch.files:
        if fr.skipped:
            continue
        if fr.error:
            status = "error"
            spans = advisory = blocking = findings = "—"
        elif fr.blocking_count:
            status = "**BLOCKING**"
            spans = str(fr.span_count)
            findings = str(fr.finding_count)
            blocking = str(fr.blocking_count)
            advisory = str(fr.advisory_count)
        else:
            status = "ok"
            spans = str(fr.span_count)
            findings = str(fr.finding_count)
            blocking = str(fr.blocking_count)
            advisory = str(fr.advisory_count)
        lines.append(
            f"| `{fr.relative_path}` | {spans} | {findings} | {blocking} | {advisory} | {status} |"
        )

    lines.append("")

    errors = [fr for fr in batch.files if fr.error]
    if errors:
        lines += ["## Errors", ""]
        for fr in errors:
            lines.append(f"- `{fr.relative_path}`: {fr.error}")
        lines.append("")

    blocking_files = [fr for fr in batch.files if fr.blocking_count]
    if blocking_files:
        lines += ["## Blocking Findings", ""]
        for fr in blocking_files:
            report_path = f"files/{fr.relative_path}/report.md"
            lines.append(
                f"- `{fr.relative_path}`: {fr.blocking_count} blocking finding(s)"
                f" — see `{report_path}`"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def write_run(
    run_dir: Path,
    container: SourceContainer,
    findings: list[Finding],
    manifest: RunManifest,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    (run_dir / "model.json").write_text(
        json.dumps(_container_to_dict(container), indent=2), encoding="utf-8"
    )
    (run_dir / "findings.json").write_text(
        json.dumps([_finding_to_dict(f) for f in findings], indent=2), encoding="utf-8"
    )
    (run_dir / "manifest.json").write_text(
        json.dumps(dataclasses.asdict(manifest), indent=2), encoding="utf-8"
    )
    (run_dir / "report.md").write_text(
        _build_report(container, findings, manifest), encoding="utf-8"
    )


def write_batch_run(
    batch_run_dir: Path,
    batch_manifest: BatchManifest,
    file_results: list[tuple[str, SourceContainer, list[Finding], RunManifest]],
) -> None:
    batch_run_dir.mkdir(parents=True, exist_ok=True)
    for rel_path, container, findings, manifest in file_results:
        write_run(batch_run_dir / "files" / rel_path, container, findings, manifest)
    (batch_run_dir / "index.json").write_text(
        json.dumps(dataclasses.asdict(batch_manifest), indent=2), encoding="utf-8"
    )
    (batch_run_dir / "summary.md").write_text(
        _build_batch_summary(batch_manifest), encoding="utf-8"
    )
