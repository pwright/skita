"""skita CLI — entry point for `skita scan`."""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import __version__


def _count_spans(spans) -> int:
    total = len(spans)
    for s in spans:
        total += _count_spans(s.members)
    return total


def cmd_scan(args: argparse.Namespace) -> int:
    from . import analyzer, artifacts, parser, reviews
    from .model import RunManifest

    source_path = Path(args.source)
    sidecar_dir = Path(args.sidecar)

    if not source_path.exists():
        print(f"error: {source_path}: no such file or directory", file=sys.stderr)
        return 1

    if source_path.is_dir():
        return cmd_scan_dir(args, source_path)

    container = parser.parse_file(source_path)

    review_store = reviews.load(sidecar_dir)
    reviews.apply(container.spans, review_store)

    findings = analyzer.analyze(container)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_name = args.run_name or f"{ts}-{container.source_hash[:8]}"
    run_dir = sidecar_dir / "runs" / run_name

    span_count = _count_spans(container.spans)
    manifest = RunManifest(
        skita_version=__version__,
        source_path=str(source_path.resolve()),
        source_hash=container.source_hash,
        run_id=run_name,
        timestamp=ts,
        span_count=span_count,
        finding_count=len(findings),
    )

    artifacts.write_run(run_dir, container, findings, manifest)

    blocking = [f for f in findings if f.severity == "blocking"]
    advisory = [f for f in findings if f.severity == "advisory"]

    print(f"run:      {run_dir}")
    print(f"spans:    {span_count}")
    print(f"findings: {len(findings)}  ({len(blocking)} blocking, {len(advisory)} advisory)")

    if blocking:
        print("\nBLOCKING:", file=sys.stderr)
        for f in blocking:
            print(f"  [{f.rule}] line {f.start_line}: {f.message}", file=sys.stderr)
        return 1

    return 0


def cmd_scan_dir(args: argparse.Namespace, source_path: Path) -> int:
    from . import analyzer, artifacts, ignore, parser, reviews
    from .model import BatchManifest, FileResult, RunManifest

    sidecar_dir = Path(args.sidecar)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_id = args.run_name or f"{ts}-{source_path.name}"
    batch_run_dir = sidecar_dir / "runs" / run_id

    sidecar_skignore = sidecar_dir / ".skignore"
    cwd_skignore = Path.cwd() / ".skignore"
    if not sidecar_skignore.exists() and cwd_skignore.exists():
        sidecar_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cwd_skignore, sidecar_skignore)
    patterns = ignore.load(sidecar_dir)
    review_store = reviews.load(sidecar_dir)

    all_md = sorted(source_path.rglob("*.md"))

    file_results_data: list[tuple] = []
    file_results_meta: list[FileResult] = []
    ignored_count = error_count = 0
    total_spans = total_findings = total_blocking = total_advisory = 0

    for md_file in all_md:
        rel_str = str(md_file.relative_to(source_path))

        if ignore.is_ignored(rel_str, patterns):
            ignored_count += 1
            file_results_meta.append(FileResult(
                relative_path=rel_str, source_path=str(md_file.resolve()),
                source_hash="", run_id=run_id,
                span_count=0, finding_count=0, blocking_count=0, advisory_count=0,
                skipped=True, error="",
            ))
            continue

        try:
            container = parser.parse_file(md_file)
            reviews.apply(container.spans, review_store)
            findings = analyzer.analyze(container)

            span_count = _count_spans(container.spans)
            blocking = [f for f in findings if f.severity == "blocking"]
            advisory = [f for f in findings if f.severity == "advisory"]

            manifest = RunManifest(
                skita_version=__version__,
                source_path=str(md_file.resolve()),
                source_hash=container.source_hash,
                run_id=run_id, timestamp=ts,
                span_count=span_count, finding_count=len(findings),
            )
            file_results_data.append((rel_str, container, findings, manifest))
            file_results_meta.append(FileResult(
                relative_path=rel_str, source_path=str(md_file.resolve()),
                source_hash=container.source_hash, run_id=run_id,
                span_count=span_count, finding_count=len(findings),
                blocking_count=len(blocking), advisory_count=len(advisory),
                skipped=False, error="",
            ))
            total_spans += span_count
            total_findings += len(findings)
            total_blocking += len(blocking)
            total_advisory += len(advisory)

        except Exception as exc:
            error_count += 1
            file_results_meta.append(FileResult(
                relative_path=rel_str, source_path=str(md_file.resolve()),
                source_hash="", run_id=run_id,
                span_count=0, finding_count=0, blocking_count=0, advisory_count=0,
                skipped=False, error=str(exc),
            ))

    processed_count = len(all_md) - ignored_count - error_count
    batch_manifest = BatchManifest(
        skita_version=__version__, source_dir=str(source_path.resolve()),
        run_id=run_id, timestamp=ts,
        file_count=len(all_md), ignored_count=ignored_count,
        processed_count=processed_count, error_count=error_count,
        total_span_count=total_spans, total_finding_count=total_findings,
        blocking_count=total_blocking, advisory_count=total_advisory,
        files=file_results_meta,
    )

    artifacts.write_batch_run(batch_run_dir, batch_manifest, file_results_data)

    print(f"run:      {batch_run_dir}")
    print(f"files:    {processed_count} processed, {ignored_count} ignored, {error_count} errors")
    print(f"spans:    {total_spans}")
    print(f"findings: {total_findings}  ({total_blocking} blocking, {total_advisory} advisory)")

    if error_count:
        print("\nERRORS:", file=sys.stderr)
        for fr in [f for f in file_results_meta if f.error]:
            print(f"  {fr.relative_path}: {fr.error}", file=sys.stderr)

    if total_blocking:
        print("\nBLOCKING:", file=sys.stderr)
        for fr in [f for f in file_results_meta if f.blocking_count]:
            print(f"  {fr.relative_path}: {fr.blocking_count} blocking finding(s)", file=sys.stderr)
        return 1

    return 0


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="skita",
        description="Read-only Markdown documentation analysis sidecar",
    )
    ap.add_argument("--version", action="version", version=f"skita {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Scan a Markdown source file or directory")
    scan_p.add_argument("source", help="Path to Markdown source file or directory")
    scan_p.add_argument(
        "--sidecar",
        default="./skita-sidecar",
        help="Sidecar root directory (default: ./skita-sidecar)",
    )
    scan_p.add_argument("--run-name", help="Override the generated run name")

    args = ap.parse_args()
    sys.exit(cmd_scan(args))
