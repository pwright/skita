"""Tests for src/skita/convert.py — 5 tests per issue 0021-test-strategy.md."""
import json

import pytest

from skita.convert import convert_span, run_convert


# ---------------------------------------------------------------------------
# Test 1: Indent-based bullet-list exit
# Prose at step indent level exits <ul>, landing outside the last <li>.
# ---------------------------------------------------------------------------

def test_bullet_exit_at_step_level():
    lines = [
        "**Procedure**",
        "1. Step cmd",
        "* Bullet one",
        "Prose after bullets.",
    ]
    span = {"anchor": "t1", "heading": "T", "content_lines": lines, "intro_lines": [], "members": []}
    xml = convert_span(span, "task", "topic")
    assert "</ul>" in xml
    assert "<p>Prose after bullets.</p>" in xml
    assert xml.index("</ul>") < xml.index("<p>Prose after bullets.</p>")


# ---------------------------------------------------------------------------
# Test 2: Nested bullet sub-content
# Paragraph and codeblock under a bullet item go inside <li>, not after </ul>.
# ---------------------------------------------------------------------------

def test_nested_bullet_sub_content_inside_li():
    lines = [
        "**Procedure**",
        "1. Step cmd",
        "* Bullet item",
        "  Sub-paragraph.",
        "  ```bash",
        "  sub code",
        "  ```",
    ]
    span = {"anchor": "t2", "heading": "T", "content_lines": lines, "intro_lines": [], "members": []}
    xml = convert_span(span, "task", "topic")
    li_start = xml.index("<li>Bullet item")
    li_end = xml.index("</li>", li_start)
    codeblock_pos = xml.index("<codeblock", li_start)
    assert codeblock_pos < li_end, "codeblock must be inside <li>, not after </li>"


# ---------------------------------------------------------------------------
# Test 3: Provisional-ID spans skipped with stderr warning
# Spans whose anchor starts with '~' are not written; a warning goes to stderr.
# ---------------------------------------------------------------------------

def test_provisional_id_skip(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source_path = str(tmp_path / "mydir" / "file.md")
    model = {
        "source_path": source_path,
        "source_hash": "abc",
        "frontmatter": {},
        "spans": [{
            "topic_id": "~abc12345",
            "topic_type": "task",
            "confidence": "declared",
            "heading": "Some heading",
            "heading_depth": 1,
            "source_path": source_path,
            "start_line": 1,
            "end_line": 10,
            "role": "topic",
            "anchor": "~abc12345",
            "intro_lines": [],
            "members": [],
            "content_lines": [],
        }],
        "candidates": [],
    }
    (run_dir / "model.json").write_text(json.dumps(model), encoding="utf-8")
    mapping_path = tmp_path / "mapping.csv"
    mapping_path.write_text("anchor_id,source_dir,target_dir,notes\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    rc = run_convert(run_dir, output_dir, mapping_path)

    assert rc == 0
    assert list(output_dir.rglob("*.dita")) == [], "no DITA file should be written for provisional ID"
    err = capsys.readouterr().err
    assert "unanchored" in err
    assert "~abc12345" in err


# ---------------------------------------------------------------------------
# Test 4: Unmapped spans — warning to stderr, exit 0, no file written
# ---------------------------------------------------------------------------

def test_unmapped_span_warning(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    source_path = str(tmp_path / "mydir" / "file.md")
    model = {
        "source_path": source_path,
        "source_hash": "abc",
        "frontmatter": {},
        "spans": [{
            "topic_id": "my-topic",
            "topic_type": "task",
            "confidence": "declared",
            "heading": "My topic",
            "heading_depth": 1,
            "source_path": source_path,
            "start_line": 1,
            "end_line": 10,
            "role": "topic",
            "anchor": "my-topic",
            "intro_lines": [],
            "members": [],
            "content_lines": [],
        }],
        "candidates": [],
    }
    (run_dir / "model.json").write_text(json.dumps(model), encoding="utf-8")
    mapping_path = tmp_path / "mapping.csv"
    # No entry for (my-topic, mydir)
    mapping_path.write_text("anchor_id,source_dir,target_dir,notes\n", encoding="utf-8")
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    rc = run_convert(run_dir, output_dir, mapping_path)

    assert rc == 0
    assert list(output_dir.rglob("*.dita")) == [], "no DITA file should be written for unmapped span"
    err = capsys.readouterr().err
    assert "skipping" in err.lower()
    assert "my-topic" in err


# ---------------------------------------------------------------------------
# Test 5: End-to-end smoke test against test/fixtures/procedure.md
# ---------------------------------------------------------------------------

EXPECTED_PROCEDURE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE task PUBLIC "-//OASIS//DTD DITA Task//EN" "../../dtd/libs/fmdita/dita_resources/DITA-1.3/dtd/technicalContent/dtd/task.dtd">
<task id="my-procedure">
  <title>My Procedure</title>
  <shortdesc>An intro paragraph.</shortdesc>
  <taskbody>
    <prereq>
      <ul>
        <li>Pre-req one</li>
        <li>Pre-req two</li>
      </ul>
    </prereq>
    <steps>
      <step>
        <cmd>First step
</cmd>
        <info>
          <p>Some step info.</p>
        </info>
      </step>
      <step>
        <cmd>Second step
</cmd>
        <info>
          <codeblock outputclass="language-bash">some command</codeblock>
        </info>
      </step>
    </steps>
  </taskbody>
</task>"""


def test_smoke_procedure(fixtures_dir):
    from skita import parser
    container = parser.parse_file(fixtures_dir / "procedure.md")
    assert len(container.spans) == 1
    span = container.spans[0]
    span_dict = {
        "anchor": span.anchor,
        "heading": span.heading,
        "content_lines": span.content_lines,
        "intro_lines": span.intro_lines,
        "members": [],
    }
    xml = convert_span(span_dict, span.topic_type, span.role)
    assert xml == EXPECTED_PROCEDURE_XML
