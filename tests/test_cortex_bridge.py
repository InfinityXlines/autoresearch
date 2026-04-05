"""Tests for the Cortex bridge."""
import json
import tempfile
from pathlib import Path

from tools.cortex_bridge import collect_policy_history, collect_weekly_reports


def test_collect_policy_history():
    """Policy history JSONL is collected into ingestable entries."""
    with tempfile.TemporaryDirectory() as d:
        history = Path(d) / "policy.history.jsonl"
        history.write_text(
            json.dumps({"timestamp": "2026-04-05", "changes": ["weight_a: 0.5->0.6"]}) + "\n"
            + json.dumps({"timestamp": "2026-04-04", "changes": ["weight_b: 0.3->0.4"]}) + "\n"
        )
        entries = collect_policy_history(history)
        assert len(entries) == 2
        assert "weight_a" in entries[0]["text"]


def test_collect_weekly_reports():
    """Weekly report files are collected."""
    with tempfile.TemporaryDirectory() as d:
        reports = Path(d) / "reports"
        reports.mkdir()
        (reports / "weekly-2026-04-05.md").write_text("# Weekly Report\n\nAll good.")
        results = collect_weekly_reports(reports)
        assert len(results) == 1
        assert results[0].name == "weekly-2026-04-05.md"


def test_collect_policy_history_missing_file():
    """Missing policy history returns empty list."""
    entries = collect_policy_history(Path("/nonexistent/policy.history.jsonl"))
    assert entries == []
