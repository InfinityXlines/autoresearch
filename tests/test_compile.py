"""Tests for the wiki compiler."""
import json
import tempfile
from pathlib import Path

from tools.common import write_frontmatter, read_frontmatter
from tools.compile import (
    detect_topic,
    generate_article_content,
    update_topic_index,
    update_master_index,
    update_backlinks,
    compile_incremental,
    get_existing_topics,
)


def _make_raw(d: Path, title: str, topic: str, body: str) -> Path:
    """Helper to create a raw source file."""
    raw_dir = d / "raw"
    raw_dir.mkdir(exist_ok=True)
    p = raw_dir / f"{title.lower().replace(' ', '-')}.md"
    write_frontmatter(p, {
        "title": title,
        "topic": topic,
        "source_type": "text",
        "ingested": "2026-04-05T00:00:00Z",
    }, body)
    return p


def _make_wiki(d: Path) -> Path:
    """Helper to create a minimal wiki structure."""
    wiki = d / "wiki"
    (wiki / "topics").mkdir(parents=True, exist_ok=True)
    return wiki


def test_detect_topic_from_frontmatter():
    """Topic detection uses frontmatter topic field."""
    with tempfile.TemporaryDirectory() as d:
        p = _make_raw(Path(d), "Test", "agent-architecture", "Some content")
        assert detect_topic(p) == "agent-architecture"


def test_detect_topic_uncategorized():
    """Missing topic defaults to uncategorized."""
    with tempfile.TemporaryDirectory() as d:
        raw_dir = Path(d) / "raw"
        raw_dir.mkdir()
        p = raw_dir / "test.md"
        write_frontmatter(p, {"title": "Test", "source_type": "text"}, "body")
        assert detect_topic(p) == "uncategorized"


def test_update_topic_index_creates_index():
    """Topic index is created when it doesn't exist."""
    with tempfile.TemporaryDirectory() as d:
        wiki = _make_wiki(Path(d))
        topic_dir = wiki / "topics" / "test-topic"
        topic_dir.mkdir(parents=True)
        article = topic_dir / "article.md"
        write_frontmatter(article, {"title": "Test Article"}, "Content")
        update_topic_index(topic_dir)
        index = topic_dir / "index.md"
        assert index.exists()
        _, body = read_frontmatter(index)
        assert "Test Article" in body


def test_update_master_index():
    """Master index lists all topics."""
    with tempfile.TemporaryDirectory() as d:
        wiki = _make_wiki(Path(d))
        for topic in ["alpha", "beta"]:
            td = wiki / "topics" / topic
            td.mkdir()
            write_frontmatter(td / "index.md", {"title": topic.title()}, f"About {topic}")
        update_master_index(wiki)
        index = wiki / "index.md"
        assert index.exists()
        _, body = read_frontmatter(index)
        assert "Alpha" in body
        assert "Beta" in body


def test_update_backlinks():
    """Backlinks file tracks wikilink references."""
    with tempfile.TemporaryDirectory() as d:
        wiki = _make_wiki(Path(d))
        td = wiki / "topics" / "test"
        td.mkdir(parents=True)
        write_frontmatter(td / "a.md", {"title": "A"}, "See [[test/b]]")
        write_frontmatter(td / "b.md", {"title": "B"}, "No links here")
        update_backlinks(wiki)
        bl = wiki / "backlinks.md"
        assert bl.exists()
        content = bl.read_text()
        assert "test/b" in content


def test_get_existing_topics():
    """Lists existing topic directories."""
    with tempfile.TemporaryDirectory() as d:
        wiki = _make_wiki(Path(d))
        for name in ["alpha", "beta", "gamma"]:
            (wiki / "topics" / name).mkdir()
        topics = get_existing_topics(wiki)
        assert set(topics) == {"alpha", "beta", "gamma"}
