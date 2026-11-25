from skita import parser


def test_parse_concept(fixtures_dir):
    c = parser.parse_file(fixtures_dir / "concept.md")
    assert len(c.spans) == 1
    span = c.spans[0]
    assert span.role == "topic"
    assert span.topic_type == "concept"
    assert span.topic_id == "my-concept"


def test_parse_task(fixtures_dir):
    c = parser.parse_file(fixtures_dir / "task.md")
    assert len(c.spans) == 1
    assert c.spans[0].topic_type == "task"


def test_parse_assembly_structure(fixtures_dir):
    c = parser.parse_file(fixtures_dir / "assembly.md")
    assert len(c.spans) == 1
    top = c.spans[0]
    assert top.role == "assembly"
    assert len(top.members) == 2


def test_parse_assembly_intro(fixtures_dir):
    c = parser.parse_file(fixtures_dir / "assembly.md")
    assert c.spans[0].intro_lines


def test_parse_unmarked(fixtures_dir):
    c = parser.parse_file(fixtures_dir / "unmarked.md")
    assert len(c.spans) == 0
    assert len(c.candidates) == 2


def test_parse_source_hash_deterministic(fixtures_dir):
    c1 = parser.parse_file(fixtures_dir / "concept.md")
    c2 = parser.parse_file(fixtures_dir / "concept.md")
    assert len(c1.source_hash) == 64
    assert c1.source_hash == c2.source_hash
