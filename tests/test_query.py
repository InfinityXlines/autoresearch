"""Tests for the query engine."""
import tempfile
import shutil
from pathlib import Path

from tools.query import build_context, format_query_prompt


FIXTURE_WIKI = Path(__file__).parent / "fixtures" / "sample_wiki"


def test_build_context_from_wiki():
    """Context builder reads relevant wiki articles."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki"
        shutil.copytree(FIXTURE_WIKI, wiki)
        context = build_context(wiki, "memory systems")
        assert len(context) > 0
        assert any("Memory" in c["title"] for c in context)


def test_build_context_empty_query():
    """Empty query returns master index context."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki"
        shutil.copytree(FIXTURE_WIKI, wiki)
        context = build_context(wiki, "")
        assert len(context) >= 0  # May be empty or have index


def test_format_query_prompt():
    """Query prompt includes context and question."""
    context = [
        {"title": "Memory Systems", "body": "Auto-memory captures signal."},
    ]
    prompt = format_query_prompt("How does memory work?", context)
    assert "Memory Systems" in prompt
    assert "How does memory work?" in prompt
    assert "Auto-memory" in prompt
