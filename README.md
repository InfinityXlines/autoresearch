# Autoresearch

LLM-powered knowledge base system for multi-agent fleets. Inspired by [Andrej Karpathy's "LLM Knowledge Bases"](https://x.com/karpathy) concept.

## What It Does

- **Ingests** raw data (articles, papers, files, URLs, text) into per-agent knowledge bases
- **Compiles** raw sources into structured, interlinked wiki articles via LLM
- **Searches** across all knowledge bases with full-text search and ranking
- **Lints** wikis for health issues (staleness, orphans, dead links, thin coverage)
- **Queries** the knowledge base with complex questions, files answers back

## Architecture

```
Per-agent KBs (~/.autoresearch/agents/<name>/)
  raw/       -> ingested sources
  wiki/      -> LLM-compiled articles (Obsidian-compatible)
  outputs/   -> Q&A results

Shared wiki (~/shared-memory/wiki/)
  -> cross-fleet knowledge
```

## Quick Start

```bash
# Install
git clone https://github.com/InfinityXlines/autoresearch.git
cd autoresearch && bash setup.sh

# Ingest a source
ar ingest --agent jade --text "Key insight about X" --topic "research"

# Ingest a URL
ar ingest --agent jade --url "https://example.com/article"

# Search
ar search --agent jade "self-evolution"

# Health check
ar lint --agent jade

# Q&A
ar query --agent jade "What patterns have worked?"

# File answer back into wiki
ar query --agent jade --file "Summarize all findings on topic X"
```

## Integration

- **Auto-dream:** Full recompile + lint runs during dream cycles (Phase 2.7)
- **Cortex:** Telemetry bridge feeds policy changes and reports into the wiki
- **Obsidian:** Open any `wiki/` directory as a vault for visual browsing + graph view

## Fleet Support

| Agent | KB Path | Focus |
|-------|---------|-------|
| Jade | `~/.autoresearch/agents/jade/` | Research, architecture, self-improvement |
| Katana | `~/.autoresearch/agents/katana/` | Build patterns, code architecture |
| Magdalena | `~/.autoresearch/agents/magdalena/` | Communication patterns, user context |

## Tests

```bash
python3 -m pytest tests/ -v
```

## License

MIT
