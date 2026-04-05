# Autoresearch — LLM Agent Instructions

You are working on the Autoresearch knowledge base system. This is a Python CLI tool that ingests raw data, compiles it into structured Obsidian-compatible wikis, and supports search, linting, and Q&A.

## Quick Orientation

- **What it does:** Raw sources → LLM-compiled wiki → search/query/lint → answers filed back
- **Language:** Python 3.11+, only dependency is PyYAML
- **Tests:** `python3 -m pytest tests/ -v` (run from repo root)
- **CLI:** `ar <command>` wrapper or `python3 -m tools.<command>`

## Key Files

| File | Purpose |
|------|---------|
| `tools/common.py` | Shared utilities: config loading, path resolution, frontmatter, locking |
| `tools/ingest.py` | Source intake: text, file, URL, pipe → normalized markdown in `raw/` |
| `tools/compile.py` | Wiki compiler: raw → articles, indexes, backlinks (incremental + full) |
| `tools/search.py` | Full-text search with scoring and ranking |
| `tools/lint.py` | Health checks: orphans, dead links, staleness, coverage |
| `tools/query.py` | Q&A engine: search context → LLM prompt → answer (optionally filed back) |
| `tools/cortex_bridge.py` | Cortex telemetry → autoresearch ingest bridge |
| `templates/config.yaml` | Default configuration template |

## Architecture

```
~/.autoresearch/
  config.yaml              ← Global config
  agents/<name>/
    raw/                   ← Ingested sources (markdown + frontmatter)
      .quarantine/         ← Failed ingests
    wiki/                  ← Compiled articles (Obsidian-compatible)
      topics/<slug>/       ← Topic directories with index.md + articles
      index.md             ← Master index
      backlinks.md         ← Auto-generated backlinks
    outputs/               ← Q&A results
    .compile-state.json    ← Tracks what's been compiled
```

## Conventions

- All tools use relative imports (`from .common import ...`)
- Tests import as `from tools.ingest import ...` — run pytest from repo root
- Every markdown file has YAML frontmatter (title, topic, tags, created, modified)
- Wiki articles use `[[wikilinks]]` for inter-article links
- Config lives at `~/.autoresearch/config.yaml`, loaded by `common.load_config()`
- File locking via `fcntl.flock()` for shared wiki writes

## Running Tests

```bash
cd /path/to/autoresearch
python3 -m pytest tests/ -v
```

All 33 tests should pass. Tests use `tempfile.TemporaryDirectory()` — no side effects.

## Adding New Tools

1. Create `tools/newtool.py` with a `main()` function and argparse CLI
2. Import shared utilities from `.common`
3. Create `tests/test_newtool.py`
4. The `ar` wrapper auto-discovers tools by filename — no registration needed

## Making Changes

- Keep tools independent — each tool imports only from `.common` (except `query.py` which also imports from `.search`, and `cortex_bridge.py` which imports from `.ingest`)
- Always update `.compile-state.json` when modifying compilation behavior
- Maintain backward compatibility with existing wiki structures
- Run the full test suite before committing
