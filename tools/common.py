"""Common utilities for autoresearch tools."""
from __future__ import annotations

import fcntl
import json
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".autoresearch" / "config.yaml"
DEFAULT_SHARED_WIKI = Path.home() / "shared-memory" / "wiki"

DEFAULT_CONFIG = {
    "version": 1,
    "shared_wiki_path": str(DEFAULT_SHARED_WIKI),
    "agents": {},
    "search": {"max_results": 20, "snippet_length": 200},
    "lint": {
        "check_staleness": True,
        "staleness_threshold_days": 30,
        "check_orphans": True,
        "check_dead_links": True,
        "suggest_connections": True,
    },
    "llm": {
        "provider": "claude-cli",
        "model": "claude-sonnet-4-6",
        "timeout": 120,
    },
}


def load_config(path: Path | None = None) -> dict:
    """Load config from YAML file, falling back to defaults."""
    cfg_path = path or DEFAULT_CONFIG_PATH
    if cfg_path.exists():
        with open(cfg_path) as f:
            user_cfg = yaml.safe_load(f) or {}
        # Merge with defaults
        merged = {**DEFAULT_CONFIG, **user_cfg}
        for key in ("search", "lint", "llm"):
            if key in user_cfg and isinstance(user_cfg[key], dict):
                merged[key] = {**DEFAULT_CONFIG.get(key, {}), **user_cfg[key]}
        return merged
    return dict(DEFAULT_CONFIG)


def resolve_agent_path(agent: str, config: dict | None = None) -> Path:
    """Return the base path for an agent's knowledge base."""
    cfg = config or load_config()
    agents = cfg.get("agents", {})
    if agent in agents and "path" in agents[agent]:
        return Path(agents[agent]["path"]).expanduser()
    return Path.home() / ".autoresearch" / "agents" / agent


def resolve_wiki_path(agent: str | None = None, shared: bool = False, config: dict | None = None) -> Path:
    """Return wiki path for an agent or the shared wiki."""
    cfg = config or load_config()
    if shared:
        return Path(cfg.get("shared_wiki_path", str(DEFAULT_SHARED_WIKI))).expanduser()
    if agent:
        return resolve_agent_path(agent, cfg) / "wiki"
    raise ValueError("Must specify agent or shared=True")


def ensure_dirs(agent: str, config: dict | None = None) -> None:
    """Create standard directory structure for an agent's KB."""
    base = resolve_agent_path(agent, config)
    for subdir in ["raw", "raw/.quarantine", "wiki/topics", "wiki/assets", "outputs"]:
        (base / subdir).mkdir(parents=True, exist_ok=True)


def read_frontmatter(path: Path) -> tuple[dict, str]:
    """Parse YAML frontmatter and body from a markdown file."""
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            return meta, body
    return {}, text


def write_frontmatter(path: Path, meta: dict, body: str) -> None:
    """Write a markdown file with YAML frontmatter."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fm = yaml.dump(meta, default_flow_style=False, sort_keys=False).strip()
    path.write_text(f"---\n{fm}\n---\n\n{body}", encoding="utf-8")


@contextmanager
def acquire_lock(lock_path: Path, timeout: int = 30):
    """Acquire a file lock. Raises TimeoutError if lock cannot be acquired."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = open(lock_path, "w")
    try:
        import signal

        def _timeout_handler(signum, frame):
            raise TimeoutError(f"Could not acquire lock: {lock_path}")

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        yield lock_file
    finally:
        fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def load_compile_state(agent: str, config: dict | None = None) -> dict:
    """Load compilation state for an agent."""
    path = resolve_agent_path(agent, config) / ".compile-state.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"compiled": {}, "last_full_recompile": None}


def save_compile_state(agent: str, state: dict, config: dict | None = None) -> None:
    """Save compilation state for an agent."""
    path = resolve_agent_path(agent, config) / ".compile-state.json"
    path.write_text(json.dumps(state, indent=2, default=str))


def slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:80]


def now_iso() -> str:
    """Return current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def today_prefix() -> str:
    """Return today's date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")
