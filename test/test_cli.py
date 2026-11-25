import argparse
import json
import shutil
from pathlib import Path

from skita.cli import cmd_scan, cmd_scan_dir


def _args(source, sidecar, run_name="test-run"):
    return argparse.Namespace(source=str(source), sidecar=str(sidecar), run_name=run_name)


def test_scan_single_file_exit0(fixtures_dir, tmp_path):
    args = _args(fixtures_dir / "concept.md", tmp_path)
    assert cmd_scan(args) == 0


def test_scan_single_file_artifacts(fixtures_dir, tmp_path):
    args = _args(fixtures_dir / "concept.md", tmp_path)
    cmd_scan(args)
    run_dir = tmp_path / "runs" / "test-run"
    for name in ("model.json", "findings.json", "manifest.json", "report.md"):
        assert (run_dir / name).exists(), f"missing {name}"


def test_scan_nonexistent_exit1(tmp_path):
    args = _args(tmp_path / "no-such-file.md", tmp_path)
    assert cmd_scan(args) == 1


def test_scan_dir_blocking_exit1(fixtures_dir, tmp_path):
    args = _args(fixtures_dir, tmp_path)
    result = cmd_scan_dir(args, fixtures_dir)
    assert result == 1  # duplicate_ids.md triggers blocking


def test_scan_dir_index_written(fixtures_dir, tmp_path):
    args = _args(fixtures_dir, tmp_path)
    cmd_scan_dir(args, fixtures_dir)
    index = json.loads((tmp_path / "runs" / "test-run" / "index.json").read_text())
    assert index["file_count"] >= 5
    assert index["processed_count"] + index["ignored_count"] + index["error_count"] == index["file_count"]


def _make_scan_dir(tmp_path, fixtures_dir):
    scan_dir = tmp_path / "docs"
    (scan_dir / "refdog").mkdir(parents=True)
    (scan_dir / "guide").mkdir()
    (scan_dir / "refdog" / "something.md").write_text(
        '<a id="ref-topic"></a>\n# Ref\n<!--REFERENCE-->\n\nContent.\n'
    )
    (scan_dir / "guide" / "intro.md").write_text(
        '<a id="guide-topic"></a>\n# Intro\n<!--CONCEPT-->\n\nContent.\n'
    )
    return scan_dir


def test_skignore_copied_from_cwd_to_sidecar(tmp_path, monkeypatch, fixtures_dir):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".skignore").write_text("refdog/\n")
    scan_dir = _make_scan_dir(tmp_path, fixtures_dir)
    sidecar = tmp_path / "sidecar"

    args = _args(scan_dir, sidecar)
    result = cmd_scan_dir(args, scan_dir)

    assert result == 0
    assert (sidecar / ".skignore").read_text() == "refdog/\n"
    index = json.loads((sidecar / "runs" / "test-run" / "index.json").read_text())
    assert any(f["relative_path"] == "refdog/something.md" and f["skipped"] for f in index["files"])


def test_skignore_sidecar_used_directly(tmp_path, fixtures_dir):
    scan_dir = _make_scan_dir(tmp_path, fixtures_dir)
    sidecar = tmp_path / "sidecar"
    sidecar.mkdir()
    (sidecar / ".skignore").write_text("refdog/\n")

    args = _args(scan_dir, sidecar)
    result = cmd_scan_dir(args, scan_dir)

    assert result == 0
    index = json.loads((sidecar / "runs" / "test-run" / "index.json").read_text())
    assert any(f["relative_path"] == "refdog/something.md" and f["skipped"] for f in index["files"])


def test_skignore_sidecar_takes_priority_over_cwd(tmp_path, monkeypatch, fixtures_dir):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".skignore").write_text("guide/\n")  # cwd ignores guide
    scan_dir = _make_scan_dir(tmp_path, fixtures_dir)
    sidecar = tmp_path / "sidecar"
    sidecar.mkdir()
    (sidecar / ".skignore").write_text("refdog/\n")  # sidecar ignores refdog

    args = _args(scan_dir, sidecar)
    cmd_scan_dir(args, scan_dir)

    index = json.loads((sidecar / "runs" / "test-run" / "index.json").read_text())
    skipped = {f["relative_path"] for f in index["files"] if f["skipped"]}
    assert "refdog/something.md" in skipped
    assert "guide/intro.md" not in skipped  # sidecar wins, guide is NOT ignored


def test_scan_dir_skignore(fixtures_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".skignore").write_text("duplicate_ids.md\n")

    scan_dir = tmp_path / "docs"
    scan_dir.mkdir()
    shutil.copy(fixtures_dir / "concept.md", scan_dir / "concept.md")
    shutil.copy(fixtures_dir / "duplicate_ids.md", scan_dir / "duplicate_ids.md")

    args = _args(scan_dir, tmp_path / "sidecar")
    result = cmd_scan_dir(args, scan_dir)
    index = json.loads((tmp_path / "sidecar" / "runs" / "test-run" / "index.json").read_text())
    assert result == 0
    skipped = [f for f in index["files"] if f["skipped"]]
    assert any(f["relative_path"] == "duplicate_ids.md" for f in skipped)
