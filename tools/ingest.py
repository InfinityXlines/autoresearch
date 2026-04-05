"""Autoresearch Ingester — converts raw sources into normalized markdown."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .common import (
    load_config,
    resolve_agent_path,
    ensure_dirs,
    write_frontmatter,
    read_frontmatter,
    slugify,
    today_prefix,
    now_iso,
)


def normalize_markdown(content: str, source_type: str, topic: str | None = None,
                       source_path: str | None = None, url: str | None = None) -> str:
    """Add frontmatter to raw markdown content."""
    meta = {
        "title": _extract_title(content),
        "source_type": source_type,
        "topic": topic or "uncategorized",
        "ingested": now_iso(),
    }
    if source_path:
        meta["source_path"] = source_path
    if url:
        meta["source_url"] = url

    import yaml
    fm = yaml.dump(meta, default_flow_style=False, sort_keys=False).strip()
    return f"---\n{fm}\n---\n\n{content}"


def _extract_title(content: str) -> str:
    """Extract title from first heading or first line."""
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line and not line.startswith("---"):
            return line[:80]
    return "Untitled"


def ingest_text(text: str, raw_dir: Path, topic: str | None = None) -> Path:
    """Ingest raw text into a markdown file in raw/."""
    slug = slugify(text[:60])
    filename = f"{today_prefix()}-{slug}.md"
    dest = raw_dir / filename

    # Avoid collisions
    counter = 1
    while dest.exists():
        dest = raw_dir / f"{today_prefix()}-{slug}-{counter}.md"
        counter += 1

    meta = {
        "title": text[:80],
        "source_type": "text",
        "topic": topic or "uncategorized",
        "ingested": now_iso(),
    }
    write_frontmatter(dest, meta, text)
    return dest


def ingest_file(file_path: Path, raw_dir: Path, topic: str | None = None) -> Path | None:
    """Ingest a file into raw/. Returns None if file doesn't exist (quarantined)."""
    if not file_path.exists():
        # Quarantine
        quarantine = raw_dir / ".quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        log = quarantine / f"{today_prefix()}-{file_path.name}.log"
        log.write_text(f"File not found: {file_path}\nTimestamp: {now_iso()}\n")
        return None

    content = file_path.read_text(encoding="utf-8")
    slug = slugify(file_path.stem)
    filename = f"{today_prefix()}-{slug}.md"
    dest = raw_dir / filename

    counter = 1
    while dest.exists():
        dest = raw_dir / f"{today_prefix()}-{slug}-{counter}.md"
        counter += 1

    # Check if it already has frontmatter
    if content.startswith("---"):
        meta, body = read_frontmatter(file_path)
        meta.setdefault("source_type", "file")
        meta.setdefault("topic", topic or "uncategorized")
        meta.setdefault("ingested", now_iso())
        meta["source_path"] = str(file_path)
        write_frontmatter(dest, meta, body)
    else:
        meta = {
            "title": _extract_title(content),
            "source_type": "file",
            "topic": topic or "uncategorized",
            "ingested": now_iso(),
            "source_path": str(file_path),
        }
        write_frontmatter(dest, meta, content)
    return dest


def ingest_url(url: str, raw_dir: Path, topic: str | None = None) -> Path | None:
    """Ingest a URL by fetching its content. Returns None on failure."""
    try:
        import subprocess
        # Use curl to fetch, convert to text
        result = subprocess.run(
            ["curl", "-sL", "--max-time", "30", url],
            capture_output=True, text=True, timeout=35,
        )
        if result.returncode != 0:
            raise RuntimeError(f"curl failed: {result.stderr}")
        content = result.stdout
    except Exception as e:
        quarantine = raw_dir / ".quarantine"
        quarantine.mkdir(parents=True, exist_ok=True)
        log = quarantine / f"{today_prefix()}-url-fetch.log"
        log.write_text(f"URL fetch failed: {url}\nError: {e}\nTimestamp: {now_iso()}\n")
        return None

    slug = slugify(url.split("/")[-1] or "webpage")[:40]
    filename = f"{today_prefix()}-{slug}.md"
    dest = raw_dir / filename

    meta = {
        "title": _extract_title(content),
        "source_type": "url",
        "topic": topic or "uncategorized",
        "source_url": url,
        "ingested": now_iso(),
    }
    write_frontmatter(dest, meta, content)
    return dest


def main():
    parser = argparse.ArgumentParser(description="Autoresearch Ingester")
    parser.add_argument("--agent", required=True, help="Agent name (e.g., jade)")
    parser.add_argument("--text", help="Raw text to ingest")
    parser.add_argument("--file", help="File path to ingest")
    parser.add_argument("--url", help="URL to fetch and ingest")
    parser.add_argument("--topic", help="Topic classification")
    parser.add_argument("--no-compile", action="store_true", help="Skip incremental compilation")
    args = parser.parse_args()

    config = load_config()
    ensure_dirs(args.agent, config)
    raw_dir = resolve_agent_path(args.agent, config) / "raw"

    result = None
    if args.text:
        result = ingest_text(args.text, raw_dir, args.topic)
    elif args.file:
        result = ingest_file(Path(args.file), raw_dir, args.topic)
    elif args.url:
        result = ingest_url(args.url, raw_dir, args.topic)
    elif not sys.stdin.isatty():
        # Pipe mode
        text = sys.stdin.read()
        result = ingest_text(text, raw_dir, args.topic)
    else:
        parser.error("Must provide --text, --file, --url, or pipe input")

    if result:
        print(f"Ingested: {result}")
        if not args.no_compile:
            # Trigger incremental compile (import here to avoid circular)
            try:
                from .compile import compile_incremental
                compile_incremental(args.agent, result, config)
            except ImportError:
                pass  # compile.py not yet built
    else:
        print("Ingest failed — check quarantine.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
