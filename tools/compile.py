"""Autoresearch Compiler — turns raw sources into structured wiki articles."""
from __future__ import annotations

import argparse
import re
import json
import sys
import time
from pathlib import Path

from .common import (
    load_config,
    resolve_agent_path,
    resolve_wiki_path,
    read_frontmatter,
    write_frontmatter,
    load_compile_state,
    save_compile_state,
    slugify,
    now_iso,
    acquire_lock,
)


def detect_topic(raw_path: Path) -> str:
    """Detect topic from raw source frontmatter or content."""
    meta, _ = read_frontmatter(raw_path)
    return meta.get("topic", "uncategorized")


def get_existing_topics(wiki_path: Path) -> list[str]:
    """List existing topic directory names."""
    topics_dir = wiki_path / "topics"
    if not topics_dir.exists():
        return []
    return sorted([d.name for d in topics_dir.iterdir() if d.is_dir()])


def generate_article_content(raw_path: Path, wiki_path: Path) -> tuple[str, dict]:
    """Generate wiki article content from a raw source.

    Returns (body_text, metadata_dict).
    For v1, this does structured extraction without LLM.
    The LLM-powered version will be invoked by the agent reading compile output.
    """
    meta, body = read_frontmatter(raw_path)
    title = meta.get("title", raw_path.stem)
    topic = meta.get("topic", "uncategorized")
    source_type = meta.get("source_type", "unknown")

    # Build article body from raw content
    # In v1, this is a structured pass-through with formatting
    # Agents enhance this by running compile with --llm flag
    article_body = f"# {title}\n\n"
    article_body += body.strip() + "\n"

    article_meta = {
        "title": title,
        "topic": topic,
        "tags": meta.get("tags", []),
        "sources": [str(raw_path.name)],
        "source_type": source_type,
        "created": now_iso(),
        "modified": now_iso(),
    }
    if meta.get("source_url"):
        article_meta["source_url"] = meta["source_url"]

    return article_body, article_meta


def update_topic_index(topic_dir: Path) -> None:
    """Regenerate the index.md for a topic directory."""
    articles = []
    for f in sorted(topic_dir.glob("*.md")):
        if f.name == "index.md":
            continue
        meta, _ = read_frontmatter(f)
        title = meta.get("title", f.stem)
        articles.append(f"- [[{topic_dir.name}/{f.stem}|{title}]]")

    topic_name = topic_dir.name.replace("-", " ").title()
    body = f"# {topic_name}\n\n"
    if articles:
        body += "## Articles\n\n" + "\n".join(articles) + "\n"
    else:
        body += "*No articles yet.*\n"

    meta = {
        "title": topic_name,
        "type": "index",
        "modified": now_iso(),
    }
    write_frontmatter(topic_dir / "index.md", meta, body)


def update_master_index(wiki_path: Path) -> None:
    """Regenerate the master index.md for the wiki."""
    topics = get_existing_topics(wiki_path)
    entries = []
    for topic in topics:
        topic_index = wiki_path / "topics" / topic / "index.md"
        if topic_index.exists():
            meta, _ = read_frontmatter(topic_index)
            title = meta.get("title", topic.replace("-", " ").title())
        else:
            title = topic.replace("-", " ").title()
        article_count = len([f for f in (wiki_path / "topics" / topic).glob("*.md") if f.name != "index.md"])
        entries.append(f"- [[{topic}/index|{title}]] ({article_count} articles)")

    body = "# Knowledge Base Index\n\n"
    if entries:
        body += "## Topics\n\n" + "\n".join(entries) + "\n"
    else:
        body += "*No topics yet. Ingest some sources to get started.*\n"

    meta = {"title": "Knowledge Base Index", "type": "master-index", "modified": now_iso()}
    write_frontmatter(wiki_path / "index.md", meta, body)


def update_backlinks(wiki_path: Path) -> None:
    """Scan all wiki articles for wikilinks and build a backlinks registry."""
    wikilink_pattern = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
    backlinks: dict[str, list[str]] = {}

    topics_dir = wiki_path / "topics"
    if not topics_dir.exists():
        return

    for md_file in topics_dir.rglob("*.md"):
        if md_file.name == "backlinks.md":
            continue
        rel = md_file.relative_to(topics_dir)
        source_ref = f"{rel.parent}/{rel.stem}" if rel.parent != Path(".") else rel.stem
        _, body = read_frontmatter(md_file)
        for match in wikilink_pattern.finditer(body):
            target = match.group(1).strip()
            backlinks.setdefault(target, []).append(source_ref)

    body = "# Backlinks\n\n"
    if backlinks:
        for target in sorted(backlinks.keys()):
            sources = sorted(set(backlinks[target]))
            source_links = ", ".join(f"[[{s}]]" for s in sources)
            body += f"- **[[{target}]]** <- {source_links}\n"
    else:
        body += "*No backlinks found.*\n"

    meta = {"title": "Backlinks", "type": "backlinks", "modified": now_iso()}
    write_frontmatter(wiki_path / "backlinks.md", meta, body)


def compile_incremental(agent: str, raw_path: Path, config: dict | None = None) -> Path | None:
    """Compile a single raw source into a wiki article."""
    cfg = config or load_config()
    wiki = resolve_wiki_path(agent=agent, config=cfg)
    state = load_compile_state(agent, cfg)

    # Skip if already compiled
    raw_name = raw_path.name
    if raw_name in state.get("compiled", {}):
        return None

    # Detect topic and create article
    topic = detect_topic(raw_path)
    topic_slug = slugify(topic)
    topic_dir = wiki / "topics" / topic_slug
    topic_dir.mkdir(parents=True, exist_ok=True)

    body, meta = generate_article_content(raw_path, wiki)
    article_slug = slugify(meta["title"])
    article_path = topic_dir / f"{article_slug}.md"

    # Handle collision
    counter = 1
    while article_path.exists():
        article_path = topic_dir / f"{article_slug}-{counter}.md"
        counter += 1

    write_frontmatter(article_path, meta, body)

    # Update indexes
    update_topic_index(topic_dir)
    update_master_index(wiki)
    update_backlinks(wiki)

    # Update compile state
    state.setdefault("compiled", {})[raw_name] = now_iso()
    save_compile_state(agent, state, cfg)

    print(f"Compiled: {raw_path.name} -> {article_path.relative_to(wiki)}")
    return article_path


def compile_full(agent: str | None = None, shared: bool = False, config: dict | None = None,
                 timeout: int = 600) -> dict:
    """Full recompile of an agent's wiki or the shared wiki."""
    cfg = config or load_config()
    start = time.time()
    stats = {"compiled": 0, "skipped": 0, "errors": 0, "timed_out": False}

    if shared:
        wiki = resolve_wiki_path(shared=True, config=cfg)
        # Shared wiki doesn't have a raw/ — it's compiled from agent contributions
        update_master_index(wiki)
        update_backlinks(wiki)
        return stats

    if not agent:
        raise ValueError("Must specify agent or shared=True")

    base = resolve_agent_path(agent, cfg)
    wiki = base / "wiki"
    raw_dir = base / "raw"

    if not raw_dir.exists():
        return stats

    state = load_compile_state(agent, cfg)

    # Recompile all raw sources
    raw_files = sorted(raw_dir.glob("*.md"))

    # Enforce 500-source ceiling
    if len(raw_files) > 500:
        print(f"Warning: {len(raw_files)} sources exceeds 500 ceiling. Using most recent 500.")
        raw_files = raw_files[-500:]

    for raw_path in raw_files:
        if time.time() - start > timeout:
            stats["timed_out"] = True
            print(f"Timeout after {timeout}s. Partial recompile saved.")
            break

        try:
            topic = detect_topic(raw_path)
            topic_slug = slugify(topic)
            topic_dir = wiki / "topics" / topic_slug
            topic_dir.mkdir(parents=True, exist_ok=True)

            body, meta = generate_article_content(raw_path, wiki)
            article_slug = slugify(meta["title"])
            article_path = topic_dir / f"{article_slug}.md"

            write_frontmatter(article_path, meta, body)
            state.setdefault("compiled", {})[raw_path.name] = now_iso()
            stats["compiled"] += 1
        except Exception as e:
            state.setdefault("compiled", {})[raw_path.name] = f"failed:{e}"
            stats["errors"] += 1

    # Rebuild all indexes
    for topic_dir in (wiki / "topics").iterdir():
        if topic_dir.is_dir():
            update_topic_index(topic_dir)
    update_master_index(wiki)
    update_backlinks(wiki)

    state["last_full_recompile"] = now_iso()
    save_compile_state(agent, state, cfg)

    return stats


def main():
    parser = argparse.ArgumentParser(description="Autoresearch Compiler")
    parser.add_argument("--agent", help="Agent name")
    parser.add_argument("--shared", action="store_true", help="Compile shared wiki")
    parser.add_argument("--source", help="Single source to compile (incremental)")
    parser.add_argument("--full", action="store_true", help="Full recompile")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds for full recompile")
    args = parser.parse_args()

    config = load_config()

    if args.source:
        if not args.agent and not args.shared:
            parser.error("Must specify --agent or --shared with --source")
        agent = args.agent or "shared"
        result = compile_incremental(agent, Path(args.source), config)
        if result:
            print(f"Article: {result}")
    elif args.full:
        if args.shared:
            stats = compile_full(shared=True, config=config, timeout=args.timeout)
        elif args.agent:
            stats = compile_full(agent=args.agent, config=config, timeout=args.timeout)
        else:
            parser.error("Must specify --agent or --shared with --full")
        print(f"Recompile: {stats['compiled']} compiled, {stats['errors']} errors"
              + (", TIMED OUT" if stats.get("timed_out") else ""))
    else:
        parser.error("Must specify --source or --full")


if __name__ == "__main__":
    main()
