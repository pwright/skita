"""skita CLI — entry point for `skita scan`."""
from __future__ import annotations

import argparse
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
        print(f"error: {source_path}: no such file", file=sys.stderr)
        return 1

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


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="skita",
        description="Read-only Markdown documentation analysis sidecar",
    )
    ap.add_argument("--version", action="version", version=f"skita {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser("scan", help="Scan a Markdown source file")
    scan_p.add_argument("source", help="Path to Markdown source file")
    scan_p.add_argument(
        "--sidecar",
        default="./skita-sidecar",
        help="Sidecar root directory (default: ./skita-sidecar)",
    )
    scan_p.add_argument("--run-name", help="Override the generated run name")

    args = ap.parse_args()
    sys.exit(cmd_scan(args))
