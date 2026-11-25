from skita import analyzer
from skita.model import SourceContainer, TopicSpan


def _span(topic_id, topic_type, role="topic", anchor=None,
          content_lines=None, intro_lines=None, members=None,
          start_line=1, end_line=10, heading_depth=1):
    return TopicSpan(
        topic_id=topic_id,
        topic_type=topic_type,
        confidence="declared",
        heading=f"Heading {topic_id}",
        heading_depth=heading_depth,
        source_path="fake.md",
        start_line=start_line,
        end_line=end_line,
        role=role,
        anchor=anchor,
        content_lines=content_lines or [],
        intro_lines=intro_lines or [],
        members=members or [],
    )


def _container(spans, candidates=None, frontmatter=None):
    return SourceContainer(
        source_path="fake.md",
        source_hash="abc123",
        frontmatter=frontmatter or {},
        spans=spans,
        candidates=candidates or [],
    )


def _rules(findings):
    return [f.rule for f in findings]


def test_topic_count():
    c = _container([_span("a", "concept"), _span("b", "reference")])
    findings = analyzer.analyze(c)
    tc = [f for f in findings if f.rule == "TOPIC_COUNT"]
    assert len(tc) == 1
    assert tc[0].severity == "inventory"


def test_unmarked_headings():
    c = _container([], candidates=[{"heading": "Oops", "depth": 1, "line": 3, "anchor": None}])
    findings = analyzer.analyze(c)
    uh = [f for f in findings if f.rule == "UNMARKED_HEADINGS"]
    assert len(uh) == 1
    assert uh[0].severity == "inventory"


def test_no_unmarked_headings_when_empty():
    c = _container([_span("a", "concept")])
    assert "UNMARKED_HEADINGS" not in _rules(analyzer.analyze(c))


def test_duplicate_topic_id():
    c = _container([_span("dup", "concept", start_line=1), _span("dup", "reference", start_line=5)])
    findings = analyzer.analyze(c)
    dups = [f for f in findings if f.rule == "DUPLICATE_TOPIC_ID"]
    assert len(dups) == 1
    assert dups[0].severity == "blocking"


def test_no_duplicate_when_unique():
    c = _container([_span("a", "concept"), _span("b", "reference")])
    assert "DUPLICATE_TOPIC_ID" not in _rules(analyzer.analyze(c))


def test_file_topic_type_not_allowed():
    c = _container([], frontmatter={"topic_type": "concept"})
    findings = analyzer.analyze(c)
    ft = [f for f in findings if f.rule == "FILE_TOPIC_TYPE_NOT_ALLOWED"]
    assert len(ft) == 1
    assert ft[0].severity == "advisory"


def test_assembly_intro_candidate():
    assembly = _span("asm", None, role="assembly", intro_lines=["Intro prose."])
    c = _container([assembly])
    findings = analyzer.analyze(c)
    aic = [f for f in findings if f.rule == "ASSEMBLY_INTRO_CANDIDATE"]
    assert len(aic) == 1
    assert aic[0].severity == "advisory"


def test_assembly_no_members():
    assembly = _span("asm", None, role="assembly", members=[])
    c = _container([assembly])
    findings = analyzer.analyze(c)
    anm = [f for f in findings if f.rule == "ASSEMBLY_NO_MEMBERS"]
    assert len(anm) == 1
    assert anm[0].severity == "advisory"


def test_no_ordered_steps():
    task = _span("t", "task", content_lines=["Just prose, no steps."])
    c = _container([task])
    findings = analyzer.analyze(c)
    nos = [f for f in findings if f.rule == "NO_ORDERED_STEPS"]
    assert len(nos) == 1
    assert nos[0].severity == "advisory"


def test_no_findings_clean_task():
    task = _span("t", "task", content_lines=["1. Step one", "2. Step two"])
    c = _container([task])
    findings = analyzer.analyze(c)
    non_inventory = [f for f in findings if f.severity != "inventory"]
    assert non_inventory == []
