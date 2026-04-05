"""Tests for the wiki linter."""
import tempfile
import shutil
from pathlib import Path

from tools.common import write_frontmatter
from tools.lint import lint_wiki, check_orphans, check_dead_links, check_staleness


FIXTURE_WIKI = Path(__file__).parent / "fixtures" / "sample_wiki"


def test_check_orphans_finds_uncompiled():
    """Orphan check finds raw sources not in compile state."""
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        raw = base / "raw"
        raw.mkdir()
        (raw / "source-a.md").write_text("content a")
        (raw / "source-b.md").write_text("content b")
        state = {"compiled": {"source-a.md": "2026-04-05"}}
        orphans = check_orphans(raw, state)
        assert len(orphans) == 1
        assert "source-b.md" in orphans[0]["file"]


def test_check_dead_links():
    """Dead link check finds wikilinks to non-existent articles."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki"
        td = wiki / "topics" / "test"
        td.mkdir(parents=True)
        write_frontmatter(td / "exists.md", {"title": "Exists"}, "See [[test/missing]]")
        issues = check_dead_links(wiki)
        assert len(issues) == 1
        assert "missing" in issues[0]["target"]


def test_check_staleness():
    """Staleness check flags old articles."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki" / "topics" / "test"
        wiki.mkdir(parents=True)
        write_frontmatter(wiki / "old.md", {
            "title": "Old Article",
            "modified": "2025-01-01T00:00:00Z",
        }, "Ancient content")
        issues = check_staleness(wiki.parent.parent, threshold_days=30)
        assert len(issues) == 1


def test_lint_wiki_returns_report():
    """Full lint returns a structured report."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki"
        shutil.copytree(FIXTURE_WIKI, wiki)
        raw = Path(d) / "raw"
        raw.mkdir()
        state = {"compiled": {}}
        report = lint_wiki(wiki, raw, state)
        assert "issues" in report
        assert "summary" in report
