"""Analysis rules: produce Findings from a SourceContainer."""
from __future__ import annotations

from .identity import compute_finding_id
from .model import Finding, SourceContainer, TopicSpan


def _all_spans(spans: list[TopicSpan]) -> list[TopicSpan]:
    result: list[TopicSpan] = []
    for span in spans:
        result.append(span)
        result.extend(_all_spans(span.members))
    return result


def _finding(rule: str, severity: str, topic_id: str, message: str, evidence: str,
             source_path: str, start_line: int) -> Finding:
    return Finding(
        finding_id=compute_finding_id(rule, topic_id, evidence),
        rule=rule,
        severity=severity,
        topic_id=topic_id,
        message=message,
        evidence=evidence,
        source_path=source_path,
        start_line=start_line,
    )


def _analyze_span(span: TopicSpan, findings: list[Finding]) -> None:
    if span.role == "assembly":
        # ASSEMBLY_INTRO_CANDIDATE: any intro prose is an advisory candidate
        if span.intro_lines:
            intro_text = "\n".join(span.intro_lines)
            findings.append(_finding(
                rule="ASSEMBLY_INTRO_CANDIDATE",
                severity="advisory",
                topic_id=span.topic_id,
                message=(
                    f'Assembly "{span.heading}" has {len(span.intro_lines)} line(s) of intro prose '
                    f"before its first member. Consider whether this prose has independent reader "
                    f"purpose and should become a concept topic (requires a reviewed assignment)."
                ),
                evidence=intro_text[:300],
                source_path=span.source_path,
                start_line=span.start_line,
            ))

        # ASSEMBLY_NO_MEMBERS: an assembly with no declared member spans
        if not span.members:
            findings.append(_finding(
                rule="ASSEMBLY_NO_MEMBERS",
                severity="advisory",
                topic_id=span.topic_id,
                message=f'Assembly "{span.heading}" has no declared member topic spans.',
                evidence="",
                source_path=span.source_path,
                start_line=span.start_line,
            ))

        for member in span.members:
            _analyze_span(member, findings)

    else:
        # NO_ORDERED_STEPS: task with no ordered list in content
        if span.topic_type == "task":
            has_steps = any(
                line.strip() and (line.strip()[0].isdigit() or line.strip().startswith("1."))
                for line in span.content_lines
            )
            if not has_steps:
                findings.append(_finding(
                    rule="NO_ORDERED_STEPS",
                    severity="advisory",
                    topic_id=span.topic_id,
                    message=(
                        f'Task "{span.heading}" has no ordered list steps. '
                        f"This may be an approved informal procedure."
                    ),
                    evidence="",
                    source_path=span.source_path,
                    start_line=span.start_line,
                ))


def analyze(container: SourceContainer) -> list[Finding]:
    findings: list[Finding] = []
    all_spans = _all_spans(container.spans)

    # --- Inventory findings ---

    findings.append(_finding(
        rule="TOPIC_COUNT",
        severity="inventory",
        topic_id="__container__",
        message=f"Source container has {len(all_spans)} declared topic span(s).",
        evidence="",
        source_path=container.source_path,
        start_line=1,
    ))

    if container.candidates:
        findings.append(_finding(
            rule="UNMARKED_HEADINGS",
            severity="inventory",
            topic_id="__container__",
            message=(
                f"{len(container.candidates)} unmarked heading(s) found — heuristic candidates "
                f"only, not confirmed topic spans."
            ),
            evidence=", ".join(f'"{c["heading"]}"' for c in container.candidates[:5]),
            source_path=container.source_path,
            start_line=1,
        ))

    # --- Blocking findings ---

    # Duplicate topic IDs (excluding provisional IDs — duplicates there would be structural bugs)
    seen_ids: dict[str, int] = {}
    for span in all_spans:
        if span.topic_id in seen_ids:
            findings.append(_finding(
                rule="DUPLICATE_TOPIC_ID",
                severity="blocking",
                topic_id=span.topic_id,
                message=(
                    f'Topic ID "{span.topic_id}" appears on multiple spans '
                    f"(lines {seen_ids[span.topic_id]} and {span.start_line})."
                ),
                evidence=span.topic_id,
                source_path=container.source_path,
                start_line=span.start_line,
            ))
        else:
            seen_ids[span.topic_id] = span.start_line

    # --- Advisory findings ---

    if "topic_type" in container.frontmatter:
        findings.append(_finding(
            rule="FILE_TOPIC_TYPE_NOT_ALLOWED",
            severity="advisory",
            topic_id="__container__",
            message=(
                'File frontmatter contains "topic_type", which is not allowed at file level. '
                "Use span markers instead."
            ),
            evidence=f"topic_type: {container.frontmatter['topic_type']}",
            source_path=container.source_path,
            start_line=1,
        ))

    for span in container.spans:
        _analyze_span(span, findings)

    return findings
