"""Tests for the search engine."""
import tempfile
import shutil
from pathlib import Path

from tools.search import search_wiki, rank_results


FIXTURE_WIKI = Path(__file__).parent / "fixtures" / "sample_wiki"


def test_search_finds_matching_articles():
    """Search returns articles containing the query term."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki"
        shutil.copytree(FIXTURE_WIKI, wiki)
        results = search_wiki(wiki, "memory")
        assert len(results) >= 1
        assert any("Memory Systems" in r["title"] for r in results)


def test_search_returns_snippets():
    """Results include context snippets."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki"
        shutil.copytree(FIXTURE_WIKI, wiki)
        results = search_wiki(wiki, "Cortex")
        assert len(results) >= 1
        assert any("Cortex" in r.get("snippet", "") for r in results)


def test_search_no_results():
    """Search with no matches returns empty list."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki"
        shutil.copytree(FIXTURE_WIKI, wiki)
        results = search_wiki(wiki, "xyznonexistent")
        assert results == []


def test_search_topic_scoped():
    """Topic-scoped search only searches within that topic."""
    with tempfile.TemporaryDirectory() as d:
        wiki = Path(d) / "wiki"
        shutil.copytree(FIXTURE_WIKI, wiki)
        results = search_wiki(wiki, "memory", topic="test-topic")
        assert len(results) >= 1


def test_rank_results():
    """Results are ranked by relevance (title match > body match)."""
    results = [
        {"title": "Other Article", "snippet": "mentions memory once", "score": 1},
        {"title": "Memory Systems", "snippet": "about memory systems", "score": 5},
    ]
    ranked = rank_results(results, "memory")
    assert ranked[0]["title"] == "Memory Systems"
