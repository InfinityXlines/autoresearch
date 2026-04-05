"""Autoresearch Linter — health checks for wiki quality."""
from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .common import (
    load_config,
    resolve_agent_path,
    resolve_wiki_path,
    read_frontmatter,
    load_compile_state,
)


def check_orphans(raw_dir: Path, compile_state: dict) -> list[dict]:
    """Find raw sources not yet compiled into wiki articles."""
    issues = []
    compiled = compile_state.get("compiled", {})
    if not raw_dir.exists():
        return issues
    for f in raw_dir.glob("*.md"):
        if f.name not in compiled:
            issues.append({
                "type": "orphan",
                "severity": "warning",
                "file": f.name,
                "message": f"Raw source not compiled: {f.name}",
            })
    return issues


def check_dead_links(wiki_path: Path) -> list[dict]:
    """Find wikilinks pointing to non-existent articles."""
    issues = []
    wikilink_pattern = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
    topics_dir = wiki_path / "topics"
    if not topics_dir.exists():
        return issues

    for md_file in topics_dir.rglob("*.md"):
        _, body = read_frontmatter(md_file)
        for match in wikilink_pattern.finditer(body):
            target = match.group(1).strip()
            # Resolve target path
            target_path = topics_dir / f"{target}.md"
            if not target_path.exists():
                # Try as directory index
                target_index = topics_dir / target / "index.md"
                if not target_index.exists():
                    issues.append({
                        "type": "dead_link",
                        "severity": "warning",
                        "file": str(md_file.relative_to(wiki_path)),
                        "target": target,
                        "message": f"Dead link [[{target}]] in {md_file.name}",
                    })
    return issues


def check_staleness(wiki_path: Path, threshold_days: int = 30) -> list[dict]:
    """Find articles that haven't been modified recently."""
    issues = []
    topics_dir = wiki_path / "topics"
    if not topics_dir.exists():
        return issues

    cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)

    for md_file in topics_dir.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        meta, _ = read_frontmatter(md_file)
        modified = meta.get("modified")
        if modified:
            try:
                mod_dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                if mod_dt < cutoff:
                    issues.append({
                        "type": "stale",
                        "severity": "info",
                        "file": str(md_file.relative_to(wiki_path)),
                        "modified": modified,
                        "message": f"Article stale (modified {modified}): {md_file.name}",
                    })
            except (ValueError, TypeError):
                pass
    return issues


def check_coverage(wiki_path: Path) -> list[dict]:
    """Find topics with very few articles."""
    issues = []
    topics_dir = wiki_path / "topics"
    if not topics_dir.exists():
        return issues

    for topic_dir in topics_dir.iterdir():
        if not topic_dir.is_dir():
            continue
        articles = [f for f in topic_dir.glob("*.md") if f.name != "index.md"]
        if len(articles) < 2:
            issues.append({
                "type": "thin_coverage",
                "severity": "info",
                "topic": topic_dir.name,
                "count": len(articles),
                "message": f"Topic '{topic_dir.name}' has only {len(articles)} article(s)",
            })
    return issues


def lint_wiki(wiki_path: Path, raw_dir: Path | None = None,
              compile_state: dict | None = None,
              config: dict | None = None) -> dict:
    """Run all lint checks and return a report."""
    cfg = config or load_config()
    lint_cfg = cfg.get("lint", {})
    all_issues = []

    if lint_cfg.get("check_orphans", True) and raw_dir:
        state = compile_state or {}
        all_issues.extend(check_orphans(raw_dir, state))

    if lint_cfg.get("check_dead_links", True):
        all_issues.extend(check_dead_links(wiki_path))

    if lint_cfg.get("check_staleness", True):
        threshold = lint_cfg.get("staleness_threshold_days", 30)
        all_issues.extend(check_staleness(wiki_path, threshold))

    all_issues.extend(check_coverage(wiki_path))

    warnings = [i for i in all_issues if i["severity"] == "warning"]
    infos = [i for i in all_issues if i["severity"] == "info"]

    return {
        "issues": all_issues,
        "summary": {
            "total": len(all_issues),
            "warnings": len(warnings),
            "info": len(infos),
        },
    }


def format_report(report: dict) -> str:
    """Format lint report for CLI output."""
    lines = ["=== Autoresearch Wiki Health Check ===", ""]
    summary = report["summary"]
    lines.append(f"Total issues: {summary['total']} ({summary['warnings']} warnings, {summary['info']} info)")
    lines.append("")

    for issue in report["issues"]:
        icon = "!" if issue["severity"] == "warning" else "i"
        lines.append(f"  {icon} [{issue['type']}] {issue['message']}")

    if not report["issues"]:
        lines.append("  All checks passed!")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Autoresearch Linter")
    parser.add_argument("--agent", help="Lint specific agent's wiki")
    parser.add_argument("--shared", action="store_true", help="Lint shared wiki")
    parser.add_argument("--all", action="store_true", help="Lint everything")
    parser.add_argument("--fix", action="store_true", help="Auto-fix by recompiling flagged items")
    args = parser.parse_args()

    config = load_config()

    if args.all:
        for agent_name in config.get("agents", {}):
            print(f"\n--- {agent_name} ---")
            base = resolve_agent_path(agent_name, config)
            wiki = base / "wiki"
            raw = base / "raw"
            state = load_compile_state(agent_name, config)
            report = lint_wiki(wiki, raw, state, config)
            print(format_report(report))
        print("\n--- shared ---")
        wiki = resolve_wiki_path(shared=True, config=config)
        report = lint_wiki(wiki, config=config)
        print(format_report(report))
    elif args.shared:
        wiki = resolve_wiki_path(shared=True, config=config)
        report = lint_wiki(wiki, config=config)
        print(format_report(report))
    elif args.agent:
        base = resolve_agent_path(args.agent, config)
        wiki = base / "wiki"
        raw = base / "raw"
        state = load_compile_state(args.agent, config)
        report = lint_wiki(wiki, raw, state, config)
        print(format_report(report))

        if args.fix and report["issues"]:
            print("\nAuto-fixing orphans...")
            from .compile import compile_incremental
            for issue in report["issues"]:
                if issue["type"] == "orphan":
                    raw_path = raw / issue["file"]
                    if raw_path.exists():
                        compile_incremental(args.agent, raw_path, config)
    else:
        parser.error("Must specify --agent, --shared, or --all")


if __name__ == "__main__":
    main()
