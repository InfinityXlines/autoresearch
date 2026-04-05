"""Tests for the ingester."""
import tempfile
from pathlib import Path
from unittest.mock import patch

from tools.common import read_frontmatter
from tools.ingest import ingest_text, ingest_file, normalize_markdown


def test_ingest_text_creates_raw_file():
    """Ingesting text creates a properly formatted raw file."""
    with tempfile.TemporaryDirectory() as d:
        raw_dir = Path(d) / "raw"
        raw_dir.mkdir()
        result = ingest_text(
            text="Test insight about memory systems",
            topic="agent-architecture",
            raw_dir=raw_dir,
        )
        assert result.exists()
        meta, body = read_frontmatter(result)
        assert meta["topic"] == "agent-architecture"
        assert meta["source_type"] == "text"
        assert "Test insight" in body


def test_ingest_file_copies_markdown():
    """Ingesting a markdown file normalizes and copies it."""
    with tempfile.TemporaryDirectory() as d:
        raw_dir = Path(d) / "raw"
        raw_dir.mkdir()
        source = Path(d) / "article.md"
        source.write_text("# Test Article\n\nSome content here.")
        result = ingest_file(
            file_path=source,
            raw_dir=raw_dir,
        )
        assert result.exists()
        meta, body = read_frontmatter(result)
        assert meta["source_type"] == "file"
        assert "Test Article" in body


def test_normalize_markdown_adds_frontmatter():
    """Normalizer adds frontmatter to plain markdown."""
    content = "# Hello\n\nWorld"
    result = normalize_markdown(content, source_type="text", topic="test")
    assert "---" in result
    assert "topic: test" in result
    assert "# Hello" in result


def test_ingest_text_with_no_topic():
    """Text without topic gets classified as 'uncategorized'."""
    with tempfile.TemporaryDirectory() as d:
        raw_dir = Path(d) / "raw"
        raw_dir.mkdir()
        result = ingest_text(
            text="Some random note",
            raw_dir=raw_dir,
        )
        meta, _ = read_frontmatter(result)
        assert meta["topic"] == "uncategorized"


def test_ingest_quarantines_missing_file():
    """Ingesting a non-existent file creates quarantine entry."""
    with tempfile.TemporaryDirectory() as d:
        raw_dir = Path(d) / "raw"
        raw_dir.mkdir()
        quarantine = raw_dir / ".quarantine"
        quarantine.mkdir()
        result = ingest_file(
            file_path=Path("/nonexistent/file.md"),
            raw_dir=raw_dir,
        )
        assert result is None
        # Check quarantine has an error log
        quarantine_files = list(quarantine.glob("*.log"))
        assert len(quarantine_files) == 1
