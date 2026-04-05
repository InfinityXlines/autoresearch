"""Cortex Bridge — feeds Cortex telemetry into autoresearch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .common import load_config, resolve_agent_path, now_iso
from .ingest import ingest_text, ingest_file


CORTEX_DIR = Path.home() / ".cortex"


def collect_policy_history(history_path: Path) -> list[dict]:
    """Read policy history JSONL and return ingestable entries."""
    if not history_path.exists():
        return []
    entries = []
    for line in history_path.read_text().strip().split("\n"):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            text = f"Policy change at {record.get('timestamp', 'unknown')}:\n"
            for change in record.get("changes", []):
                text += f"  - {change}\n"
            entries.append({"text": text, "timestamp": record.get("timestamp")})
        except json.JSONDecodeError:
            continue
    return entries


def collect_weekly_reports(reports_dir: Path) -> list[Path]:
    """Find weekly report files."""
    if not reports_dir.exists():
        return []
    return sorted(reports_dir.glob("weekly-*.md"))


def bridge(agent: str, config: dict | None = None) -> dict:
    """Run the Cortex -> autoresearch bridge."""
    cfg = config or load_config()
    raw_dir = resolve_agent_path(agent, cfg) / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    stats = {"policy_entries": 0, "reports": 0}

    # Ingest policy history
    history_path = CORTEX_DIR / "policy.history.jsonl"
    entries = collect_policy_history(history_path)
    for entry in entries:
        ingest_text(entry["text"], raw_dir, topic="cortex-telemetry")
        stats["policy_entries"] += 1

    # Ingest weekly reports
    reports_dir = CORTEX_DIR / "reports"
    for report in collect_weekly_reports(reports_dir):
        ingest_file(report, raw_dir, topic="cortex-telemetry")
        stats["reports"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="Cortex -> Autoresearch Bridge")
    parser.add_argument("--agent", default="jade", help="Agent name")
    args = parser.parse_args()

    config = load_config()
    stats = bridge(args.agent, config)
    print(f"Bridge: {stats['policy_entries']} policy entries, {stats['reports']} reports ingested")


if __name__ == "__main__":
    main()
