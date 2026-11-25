from pathlib import Path
from skita import ignore


def test_load_absent(tmp_path):
    assert ignore.load(tmp_path) == []


def test_load_strips_comments(tmp_path):
    (tmp_path / ".skignore").write_text("# a comment\n\ndrafts\n")
    assert ignore.load(tmp_path) == ["drafts"]


def test_load_returns_patterns(tmp_path):
    (tmp_path / ".skignore").write_text("drafts\n*.wip.md\n")
    assert ignore.load(tmp_path) == ["drafts", "*.wip.md"]


def test_is_ignored_empty_patterns():
    assert not ignore.is_ignored("drafts/wip.md", [])


def test_is_ignored_full_path_glob():
    assert ignore.is_ignored("api/ref.md", ["*.md"])


def test_is_ignored_path_component():
    assert ignore.is_ignored("drafts/wip.md", ["drafts"])


def test_is_ignored_no_match():
    assert not ignore.is_ignored("guide/intro.md", ["drafts"])


def test_is_ignored_nested_component():
    assert ignore.is_ignored("docs/drafts/wip.md", ["drafts"])


def test_load_strips_trailing_slash(tmp_path):
    (tmp_path / ".skignore").write_text("refdog/\n")
    assert ignore.load(tmp_path) == ["refdog"]


def test_is_ignored_trailing_slash_pattern(tmp_path):
    (tmp_path / ".skignore").write_text("refdog/\n")
    patterns = ignore.load(tmp_path)
    assert ignore.is_ignored("refdog/some-file.md", patterns)
