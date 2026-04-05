# Autoresearch

LLM-powered knowledge base system. Ingest raw data, compile it into structured Obsidian-compatible wikis, search, lint, and query — all maintained by your LLM, not you.

Inspired by [Andrej Karpathy's "LLM Knowledge Bases"](https://x.com/karpathy) concept.

## The Idea

> "Raw data from sources is collected, then compiled by an LLM into a .md wiki, then operated on by various CLIs by the LLM to do Q&A and to incrementally enhance the wiki, and all of it viewable in Obsidian. You rarely ever write or edit the wiki manually — it's the domain of the LLM."
> — Andrej Karpathy

Autoresearch implements this full loop:

```
Sources (URLs, files, text, PDFs)
    ↓ ingest
Raw markdown (normalized, with frontmatter)
    ↓ compile
Wiki articles (structured, interlinked, Obsidian-compatible)
    ↓ search / query / lint
Answers, health reports, new insights
    ↓ file back
Wiki grows smarter over time
```

## Requirements

- Python 3.11+
- PyYAML (`pip install pyyaml`)
- `curl` (for URL ingestion)
- Optional: [Claude Code](https://claude.ai/claude-code) CLI (for LLM-powered Q&A via `ar query`)
- Optional: [Obsidian](https://obsidian.md) (for visual wiki browsing)

## Quick Start

```bash
# 1. Clone
git clone https://github.com/InfinityXlines/autoresearch.git
cd autoresearch

# 2. Install
bash setup.sh
# This creates ~/.autoresearch/ with default config and agent directories
# Symlinks the `ar` CLI wrapper to ~/.local/bin/ar

# 3. Make sure ~/.local/bin is in your PATH
export PATH="$HOME/.local/bin:$PATH"

# 4. Ingest your first source
ar ingest --agent myagent --text "Key insight about topic X" --topic "research"

# 5. Compile into wiki
ar compile --agent myagent --full

# 6. Search
ar search --agent myagent "topic X"

# 7. Check wiki health
ar lint --agent myagent

# 8. Ask questions (requires Claude CLI)
ar query --agent myagent "What do I know about topic X?"

# 9. Open in Obsidian (optional)
open -a Obsidian ~/.autoresearch/agents/myagent/wiki/
```

## Installation Details

### What `setup.sh` Does

1. Creates `~/.autoresearch/` system directory
2. Creates agent knowledge bases (configurable — default: jade, katana, magdalena)
3. Creates shared wiki at `~/shared-memory/wiki/`
4. Copies default `config.yaml` to `~/.autoresearch/config.yaml`
5. Symlinks `ar` CLI wrapper to `~/.local/bin/ar`

### Custom Agent Names

Edit `templates/config.yaml` before running setup, or edit `~/.autoresearch/config.yaml` after:

```yaml
agents:
  my-agent-name:
    path: ~/.autoresearch/agents/my-agent-name/
    auto_compile: true
    dream_recompile: true
```

Then create the directories:
```bash
mkdir -p ~/.autoresearch/agents/my-agent-name/{raw,raw/.quarantine,wiki/topics,wiki/assets,outputs}
```

### Dependencies

```bash
pip install pyyaml   # Only required dependency
pip install pytest   # For running tests
```

## CLI Reference

All tools are accessible via the `ar` wrapper or directly as Python modules:

```bash
ar <command> [args...]
# equivalent to:
python3 -m tools.<command> [args...]
```

### `ar ingest` — Intake Raw Sources

```bash
# Ingest text
ar ingest --agent <name> --text "Your content here" --topic "topic-name"

# Ingest a file (markdown, text, or any readable file)
ar ingest --agent <name> --file /path/to/document.md --topic "topic-name"

# Ingest a URL (fetches via curl)
ar ingest --agent <name> --url "https://example.com/article" --topic "topic-name"

# Ingest from pipe/stdin
echo "piped content" | ar ingest --agent <name> --topic "topic-name"

# Ingest without auto-compiling
ar ingest --agent <name> --text "content" --no-compile
```

**What happens:** Source is normalized to markdown with YAML frontmatter and saved to `~/.autoresearch/agents/<name>/raw/`. Unless `--no-compile` is set, triggers incremental compilation into the wiki.

**If ingestion fails:** Source is quarantined to `raw/.quarantine/` with an error log.

### `ar compile` — Compile Raw Sources into Wiki

```bash
# Incremental compile (single source)
ar compile --agent <name> --source raw/filename.md

# Full recompile (all sources)
ar compile --agent <name> --full

# Full recompile with custom timeout (default: 600s)
ar compile --agent <name> --full --timeout 300

# Compile shared wiki
ar compile --shared --full
```

**What happens:**
- **Incremental:** Reads one raw source, extracts topic, creates/updates a wiki article, rebuilds indexes and backlinks.
- **Full:** Re-processes all raw sources (up to 500 per agent), rebuilds all topic indexes, master index, and backlinks.

**Output structure:**
```
wiki/
  index.md              ← Master index (auto-generated)
  backlinks.md          ← Backlink registry (auto-generated)
  topics/
    <topic-slug>/
      index.md          ← Topic index (auto-generated)
      <article-slug>.md ← Compiled article
```

### `ar search` — Full-Text Search

```bash
# Search one agent's wiki
ar search --agent <name> "query terms"

# Search across ALL agents
ar search --all "query terms"

# Search shared wiki only
ar search --shared "query terms"

# Limit to specific topic
ar search --agent <name> --topic "topic-name" "query terms"

# Limit results
ar search --agent <name> --max 5 "query terms"

# Verbose output (includes tags)
ar search --agent <name> -v "query terms"
```

**Ranking:** Title matches score 3x body matches. Exact title matches get a +10 bonus.

### `ar lint` — Wiki Health Checks

```bash
# Lint one agent's wiki
ar lint --agent <name>

# Lint shared wiki
ar lint --shared

# Lint everything
ar lint --all

# Auto-fix orphans (recompile uncompiled sources)
ar lint --agent <name> --fix
```

**Checks performed:**
| Check | What it finds |
|-------|--------------|
| Orphans | Raw sources not compiled into any article |
| Dead links | `[[wikilinks]]` pointing to non-existent articles |
| Staleness | Articles not modified in 30+ days (configurable) |
| Coverage | Topics with fewer than 2 articles |

### `ar query` — Q&A Against the Wiki

```bash
# Ask a question (prints answer)
ar query --agent <name> "What patterns have worked for X?"

# Ask across all agents
ar query --all "What's the current state of Y?"

# Ask and file the answer back into the wiki
ar query --agent <name> --file "Compare approach A vs B"

# Show which articles would be used (no LLM call)
ar query --agent <name> --context-only "topic X"
```

**How it works:**
1. Searches the wiki for relevant articles
2. Builds a context prompt with article contents
3. Sends to LLM (Claude CLI by default) for a researched answer
4. With `--file`: saves answer to `outputs/` and re-ingests into raw for future compilation

**LLM provider:** Configured in `~/.autoresearch/config.yaml`:
```yaml
llm:
  provider: "claude-cli"     # Uses `claude` CLI as subprocess
  model: "claude-sonnet-4-6" # Model for standalone queries
  timeout: 120               # Seconds per query
```

## Configuration

`~/.autoresearch/config.yaml`:

```yaml
version: 1
shared_wiki_path: ~/shared-memory/wiki/

agents:
  jade:
    path: ~/.autoresearch/agents/jade/
    auto_compile: true        # Compile on ingest
    dream_recompile: true     # Full recompile during dream cycles

search:
  max_results: 20
  snippet_length: 200

lint:
  check_staleness: true
  staleness_threshold_days: 30
  check_orphans: true
  check_dead_links: true
  suggest_connections: true

llm:
  provider: "claude-cli"
  model: "claude-sonnet-4-6"
  timeout: 120
```

## Architecture

```
~/.autoresearch/                     System root
  config.yaml                        Global configuration
  agents/
    <agent-name>/
      raw/                           Ingested sources (markdown + frontmatter)
        .quarantine/                 Failed ingests with error logs
      wiki/                          Compiled knowledge base
        index.md                     Master index
        backlinks.md                 Auto-generated backlink registry
        assets/                      Images and attachments
        topics/
          <topic-slug>/
            index.md                 Topic index
            <article-slug>.md        Compiled articles
      outputs/                       Q&A results and reports
      .compile-state.json            Compilation tracking

~/shared-memory/wiki/                Cross-agent shared knowledge
  (same structure as agent wiki/)
```

### Data Flow

```
1. INGEST: Source → normalize → add frontmatter → save to raw/
2. COMPILE: Read raw/ → detect topic → generate article → update indexes + backlinks
3. SEARCH: Query → scan wiki articles → score + rank → return snippets
4. LINT: Scan wiki → check orphans/dead links/staleness/coverage → report
5. QUERY: Question → search for context → build prompt → LLM answer → optionally file back
```

### Obsidian Compatibility

All output uses standard markdown with Obsidian conventions:
- `[[wikilinks]]` for inter-article links
- `[[topic/article]]` for cross-topic links
- YAML frontmatter with title, tags, created, modified dates
- Images as `![[image.png]]` in `wiki/assets/`
- Auto-generated backlinks

To browse visually: open any `wiki/` directory as an Obsidian vault. The graph view shows topic clusters and connections.

### Safety Features

- **File locking:** Shared wiki writes use `fcntl.flock()` to prevent corruption
- **Corpus ceiling:** Full recompile limited to 500 sources per agent (configurable)
- **Recompile timeout:** 10 minutes max during automated cycles
- **Quarantine:** Failed ingests are isolated with error logs, not silently dropped
- **Compile state tracking:** Each source's compilation status is tracked in `.compile-state.json`

## Using with Any LLM

Autoresearch is LLM-agnostic for ingest, compile (v1), search, and lint. Only `ar query` requires an LLM, and even that is configurable.

### With Claude Code (recommended)
```bash
# Claude CLI handles Q&A automatically
ar query --agent myagent "question"
```

### With Any Other LLM
```bash
# Get the context without calling an LLM
ar query --agent myagent --context-only "question"
# Copy the output into your LLM of choice

# Or pipe search results
ar search --agent myagent "topic" | your-llm-cli
```

### For LLM Agents (Automated Use)

Add this to your agent's system prompt or instructions:

```
You have access to a knowledge base via the autoresearch CLI:
- Ingest new knowledge: python3 ~/.autoresearch/tools/ingest.py --agent <name> --text "content" --topic "topic"
- Search knowledge: python3 ~/.autoresearch/tools/search.py --agent <name> "query"
- Health check: python3 ~/.autoresearch/tools/lint.py --agent <name>
- Full recompile: python3 ~/.autoresearch/tools/compile.py --agent <name> --full

Before researching a topic, search the wiki first. After learning something new, ingest it.
The wiki self-maintains — indexes, backlinks, and topic structure update automatically.
```

## Integration with Agent Systems

### Auto-Dream (Claude Code)

Add Phase 2.7 to your auto-dream cycle:
```bash
python3 ~/.autoresearch/tools/compile.py --agent <name> --full --timeout 600
python3 ~/.autoresearch/tools/lint.py --agent <name>
```

### Cortex Bridge

If you use the Cortex self-evolution engine, the bridge script ingests telemetry:
```bash
python3 ~/.autoresearch/tools/cortex_bridge.py --agent <name>
```

### CI/CD Hook

Run lint in CI to catch wiki health issues:
```bash
python3 -m tools.lint --agent <name>
# Exit code 0 = healthy, non-zero = issues found
```

## Development

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_search.py -v

# Run from repo root (required for imports)
cd ~/autoresearch && python3 -m pytest tests/ -v
```

### Project Structure

```
autoresearch/
  ar                    CLI wrapper script (bash)
  setup.sh              Installation script
  pyproject.toml        Package metadata
  README.md             This file
  CLAUDE.md             Instructions for LLM agents working on this repo
  tools/
    __init__.py
    common.py           Shared utilities (config, paths, frontmatter, locking)
    ingest.py           Source ingestion
    compile.py          Wiki compilation (incremental + full)
    search.py           Full-text search
    lint.py             Health checker
    query.py            Q&A engine
    cortex_bridge.py    Cortex telemetry bridge
  templates/
    config.yaml         Default configuration
    article.md          Wiki article template
    index.md            Topic index template
  tests/
    test_common.py      33 tests total
    test_ingest.py
    test_compile.py
    test_search.py
    test_lint.py
    test_query.py
    test_cortex_bridge.py
    fixtures/            Sample data for tests
```

## License

MIT
