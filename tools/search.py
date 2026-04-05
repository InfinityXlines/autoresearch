"""Autoresearch Search — full-text search across wiki articles."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from .common import (
    load_config,
    resolve_wiki_path,
    resolve_agent_path,
    read_frontmatter,
)


def search_wiki(wiki_path: Path, query: str, topic: str | None = None,
                max_results: int = 20, snippet_length: int = 200) -> list[dict]:
    """Search wiki articles for a query string. Returns ranked results."""
    results = []
    query_lower = query.lower()
    query_words = query_lower.split()

    topics_dir = wiki_path / "topics"
    if not topics_dir.exists():
        return []

    # Determine search scope
    if topic:
        search_dirs = [topics_dir / topic]
    else:
        search_dirs = [d for d in topics_dir.iterdir() if d.is_dir()]

    for topic_dir in search_dirs:
        if not topic_dir.exists():
            continue
        for md_file in topic_dir.glob("*.md"):
            if md_file.name in ("index.md", "backlinks.md"):
                continue
            meta, body = read_frontmatter(md_file)
            title = meta.get("title", md_file.stem)
            full_text = f"{title}\n{body}".lower()

            # Score: count query word occurrences
            score = 0
            for word in query_words:
                # Title matches worth 3x
                score += title.lower().count(word) * 3
                score += body.lower().count(word)

            if score > 0:
                # Extract snippet around first match
                snippet = _extract_snippet(body, query_words, snippet_length)
                results.append({
                    "title": title,
                    "path": str(md_file),
                    "topic": topic_dir.name,
                    "score": score,
                    "snippet": snippet,
                    "tags": meta.get("tags", []),
                })

    return rank_results(results, query)[:max_results]


def rank_results(results: list[dict], query: str) -> list[dict]:
    """Rank results by score (highest first)."""
    query_lower = query.lower()
    for r in results:
        # Boost exact title match
        if query_lower in r["title"].lower():
            r["score"] += 10
    return sorted(results, key=lambda r: r["score"], reverse=True)


def _extract_snippet(body: str, query_words: list[str], length: int) -> str:
    """Extract a context snippet around the first match."""
    body_lower = body.lower()
    best_pos = len(body)
    for word in query_words:
        pos = body_lower.find(word)
        if pos != -1 and pos < best_pos:
            best_pos = pos

    if best_pos == len(body):
        return body[:length].strip()

    start = max(0, best_pos - length // 4)
    end = min(len(body), start + length)
    snippet = body[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(body):
        snippet = snippet + "..."
    return snippet


def format_results(results: list[dict], verbose: bool = False) -> str:
    """Format search results for CLI output."""
    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. [{r['topic']}] {r['title']} (score: {r['score']})")
        if r.get("snippet"):
            lines.append(f"   {r['snippet']}")
        if verbose and r.get("tags"):
            lines.append(f"   Tags: {', '.join(r['tags'])}")
        lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Autoresearch Search")
    parser.add_argument("query", nargs="+", help="Search query")
    parser.add_argument("--agent", help="Search specific agent's wiki")
    parser.add_argument("--all", action="store_true", help="Search all agent wikis")
    parser.add_argument("--shared", action="store_true", help="Search shared wiki only")
    parser.add_argument("--topic", help="Limit to specific topic")
    parser.add_argument("--max", type=int, default=20, help="Max results")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    config = load_config()
    query = " ".join(args.query)
    all_results = []

    if args.shared:
        wiki = resolve_wiki_path(shared=True, config=config)
        all_results = search_wiki(wiki, query, args.topic, args.max)
    elif args.all:
        for agent_name in config.get("agents", {}):
            wiki = resolve_wiki_path(agent=agent_name, config=config)
            results = search_wiki(wiki, query, args.topic, args.max)
            for r in results:
                r["agent"] = agent_name
            all_results.extend(results)
        all_results = rank_results(all_results, query)[:args.max]
    elif args.agent:
        wiki = resolve_wiki_path(agent=args.agent, config=config)
        all_results = search_wiki(wiki, query, args.topic, args.max)
    else:
        parser.error("Must specify --agent, --all, or --shared")

    print(format_results(all_results, args.verbose))


if __name__ == "__main__":
    main()
