"""Autoresearch Query Engine — Q&A against the knowledge base."""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .common import (
    load_config,
    resolve_wiki_path,
    resolve_agent_path,
    read_frontmatter,
    now_iso,
    today_prefix,
    slugify,
    write_frontmatter,
)
from .search import search_wiki


def build_context(wiki_path: Path, query: str, max_articles: int = 10) -> list[dict]:
    """Build context from wiki articles relevant to the query."""
    if not query.strip():
        # Return master index if no query
        index = wiki_path / "index.md"
        if index.exists():
            meta, body = read_frontmatter(index)
            return [{"title": "Index", "body": body, "path": str(index)}]
        return []

    results = search_wiki(wiki_path, query, max_results=max_articles)
    context = []
    for r in results:
        path = Path(r["path"])
        if path.exists():
            meta, body = read_frontmatter(path)
            context.append({
                "title": r["title"],
                "body": body,
                "path": r["path"],
                "topic": r.get("topic", ""),
            })
    return context


def format_query_prompt(question: str, context: list[dict]) -> str:
    """Format a prompt with wiki context for LLM Q&A."""
    parts = ["You are answering questions using a knowledge base. Here are the relevant articles:\n"]

    for i, article in enumerate(context, 1):
        parts.append(f"--- Article {i}: {article['title']} ---")
        # Truncate long articles
        body = article["body"]
        if len(body) > 3000:
            body = body[:3000] + "\n...(truncated)"
        parts.append(body)
        parts.append("")

    parts.append(f"--- Question ---\n{question}")
    parts.append("\nAnswer based on the knowledge base above. Cite article titles when referencing information. If the knowledge base doesn't contain relevant information, say so.")

    return "\n".join(parts)


def query_with_llm(prompt: str, config: dict) -> str:
    """Send prompt to LLM and get response. Uses claude CLI for v1."""
    llm_cfg = config.get("llm", {})
    provider = llm_cfg.get("provider", "claude-cli")
    model = llm_cfg.get("model", "claude-sonnet-4-6")
    timeout = llm_cfg.get("timeout", 120)

    if provider == "claude-cli":
        try:
            result = subprocess.run(
                ["claude", "--model", model, "-p", prompt],
                capture_output=True, text=True, timeout=timeout,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return f"LLM error: {result.stderr}"
        except FileNotFoundError:
            return "[claude CLI not found — install Claude Code to enable LLM queries]"
        except subprocess.TimeoutExpired:
            return "[LLM query timed out]"
    else:
        return f"[Provider '{provider}' not implemented in v1 — use claude-cli]"


def file_answer(answer: str, question: str, agent: str, config: dict) -> Path:
    """File a Q&A answer back into the wiki as an output + ingest it."""
    base = resolve_agent_path(agent, config)
    outputs_dir = base / "outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(question[:60])
    filename = f"{today_prefix()}-{slug}.md"
    dest = outputs_dir / filename

    meta = {
        "title": question[:80],
        "type": "query-output",
        "query": question,
        "generated": now_iso(),
    }
    write_frontmatter(dest, meta, f"# {question}\n\n{answer}")

    # Also ingest back into raw for future compilation
    try:
        from .ingest import ingest_file
        raw_dir = base / "raw"
        ingest_file(dest, raw_dir, topic="query-outputs")
    except Exception:
        pass  # Non-critical

    return dest


def main():
    parser = argparse.ArgumentParser(description="Autoresearch Query Engine")
    parser.add_argument("question", nargs="+", help="Question to answer")
    parser.add_argument("--agent", help="Query specific agent's wiki")
    parser.add_argument("--all", action="store_true", help="Query across all agents")
    parser.add_argument("--shared", action="store_true", help="Query shared wiki")
    parser.add_argument("--file", action="store_true", help="File answer back into wiki")
    parser.add_argument("--context-only", action="store_true", help="Show context without LLM query")
    args = parser.parse_args()

    config = load_config()
    question = " ".join(args.question)
    all_context = []

    if args.shared:
        wiki = resolve_wiki_path(shared=True, config=config)
        all_context = build_context(wiki, question)
    elif args.all:
        for agent_name in config.get("agents", {}):
            wiki = resolve_wiki_path(agent=agent_name, config=config)
            ctx = build_context(wiki, question)
            for c in ctx:
                c["agent"] = agent_name
            all_context.extend(ctx)
    elif args.agent:
        wiki = resolve_wiki_path(agent=args.agent, config=config)
        all_context = build_context(wiki, question)
    else:
        parser.error("Must specify --agent, --all, or --shared")

    if args.context_only:
        print(f"Found {len(all_context)} relevant articles:")
        for c in all_context:
            print(f"  - {c['title']} ({c.get('agent', 'local')})")
        return

    prompt = format_query_prompt(question, all_context)

    if not all_context:
        print("No relevant articles found in the knowledge base.")
        print("Try ingesting some sources first: ar ingest --agent <name> --text '...'")
        return

    answer = query_with_llm(prompt, config)
    print(answer)

    if args.file and args.agent:
        dest = file_answer(answer, question, args.agent, config)
        print(f"\nFiled to: {dest}")


if __name__ == "__main__":
    main()
