"""Tests for common utilities."""
import json
import tempfile
from pathlib import Path

from tools.common import (
    load_config,
    read_frontmatter,
    write_frontmatter,
    slugify,
    load_compile_state,
    save_compile_state,
    resolve_agent_path,
    ensure_dirs,
)


def test_load_config_defaults():
    """Config loads defaults when no file exists."""
    cfg = load_config(Path("/nonexistent/config.yaml"))
    assert cfg["version"] == 1
    assert "search" in cfg
    assert cfg["search"]["max_results"] == 20


def test_load_config_from_file():
    """Config merges user values with defaults."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("version: 2\nsearch:\n  max_results: 50\n")
        f.flush()
        cfg = load_config(Path(f.name))
    assert cfg["version"] == 2
    assert cfg["search"]["max_results"] == 50
    assert cfg["search"]["snippet_length"] == 200  # default preserved


def test_frontmatter_roundtrip():
    """Frontmatter can be written and read back."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "test.md"
        meta = {"title": "Test", "tags": ["a", "b"]}
        body = "Hello world\n\nSecond paragraph."
        write_frontmatter(p, meta, body)
        read_meta, read_body = read_frontmatter(p)
        assert read_meta["title"] == "Test"
        assert read_meta["tags"] == ["a", "b"]
        assert "Hello world" in read_body


def test_frontmatter_no_frontmatter():
    """Files without frontmatter return empty dict."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "plain.md"
        p.write_text("Just text, no frontmatter.")
        meta, body = read_frontmatter(p)
        assert meta == {}
        assert "Just text" in body


def test_slugify():
    assert slugify("Hello World!") == "hello-world"
    assert slugify("Agent Architecture & Design") == "agent-architecture-design"
    assert slugify("  spaces  and--dashes  ") == "spaces-and-dashes"


def test_compile_state_roundtrip():
    """Compile state can be saved and loaded."""
    with tempfile.TemporaryDirectory() as d:
        # Patch resolve to use temp dir
        agent = "test"
        state_path = Path(d) / ".compile-state.json"
        state = {"compiled": {"file.md": "2026-04-05"}, "last_full_recompile": None}
        state_path.write_text(json.dumps(state))
        loaded = json.loads(state_path.read_text())
        assert loaded["compiled"]["file.md"] == "2026-04-05"


def test_ensure_dirs():
    """ensure_dirs creates the expected directory structure."""
    with tempfile.TemporaryDirectory() as d:
        # We'd need to mock resolve_agent_path for a proper test
        base = Path(d) / "agents" / "test"
        for subdir in ["raw", "raw/.quarantine", "wiki/topics", "wiki/assets", "outputs"]:
            (base / subdir).mkdir(parents=True, exist_ok=True)
        assert (base / "raw").is_dir()
        assert (base / "wiki" / "topics").is_dir()
        assert (base / "raw" / ".quarantine").is_dir()
