#!/usr/bin/env bash
set -euo pipefail

echo "=== Autoresearch Setup ==="
echo ""

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 is required but not found."
    echo "Install Python 3.11+ from https://python.org"
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
    echo "WARNING: Python $PY_VERSION detected. Python 3.11+ recommended."
fi

echo "Python $PY_VERSION detected."

# Check PyYAML
if ! python3 -c "import yaml" 2>/dev/null; then
    echo "Installing PyYAML..."
    pip install pyyaml || pip install --user pyyaml || {
        echo "ERROR: Could not install PyYAML. Run: pip install pyyaml"
        exit 1
    }
fi
echo "PyYAML: OK"

# Determine agent names from config or use defaults
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$HOME/.autoresearch/config.yaml"

if [ -f "$CONFIG_FILE" ]; then
    # Extract agent names from existing config
    AGENTS=$(python3 -c "
import yaml
with open('$CONFIG_FILE') as f:
    cfg = yaml.safe_load(f)
agents = cfg.get('agents', {})
print(' '.join(agents.keys()) if agents else 'default')
" 2>/dev/null || echo "default")
else
    AGENTS="default"
fi

# If no agents configured or using defaults, ask user
if [ "$AGENTS" = "default" ]; then
    echo ""
    echo "No agents configured. Enter agent names (space-separated)."
    echo "These are the knowledge bases that will be created."
    echo "Examples: 'myagent' or 'jade katana magdalena'"
    echo ""
    read -r -p "Agent names [default]: " USER_AGENTS
    AGENTS="${USER_AGENTS:-default}"
fi

echo ""
echo "Setting up agents: $AGENTS"

# Create system directory
mkdir -p "$HOME/.autoresearch/agents"

# Create agent subdirectories
for agent in $AGENTS; do
    for subdir in raw raw/.quarantine wiki/topics wiki/assets outputs; do
        mkdir -p "$HOME/.autoresearch/agents/$agent/$subdir"
    done
    echo "  Created KB: ~/.autoresearch/agents/$agent/"
done

# Create shared wiki
mkdir -p "$HOME/shared-memory/wiki/topics"
echo "  Created shared wiki: ~/shared-memory/wiki/"

# Generate config from template if not exists
if [ ! -f "$CONFIG_FILE" ]; then
    # Generate config dynamically based on agent names
    python3 -c "
import yaml

agents = {}
for name in '$AGENTS'.split():
    agents[name] = {
        'path': f'~/.autoresearch/agents/{name}/',
        'auto_compile': True,
        'dream_recompile': True,
    }

config = {
    'version': 1,
    'shared_wiki_path': '~/shared-memory/wiki/',
    'agents': agents,
    'search': {'max_results': 20, 'snippet_length': 200},
    'lint': {
        'check_staleness': True,
        'staleness_threshold_days': 30,
        'check_orphans': True,
        'check_dead_links': True,
        'suggest_connections': True,
    },
    'llm': {
        'provider': 'claude-cli',
        'model': 'claude-sonnet-4-6',
        'timeout': 120,
    },
}

with open('$CONFIG_FILE', 'w') as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)
print('  Created config: ~/.autoresearch/config.yaml')
"
fi

# Make ar executable and symlink
chmod +x "$SCRIPT_DIR/ar"

mkdir -p "$HOME/.local/bin"
ln -sf "$SCRIPT_DIR/ar" "$HOME/.local/bin/ar"
echo "  Symlinked: ar -> ~/.local/bin/ar"

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo ""
    echo "NOTE: ~/.local/bin is not in your PATH."
    echo "Add this to your shell profile (~/.bashrc, ~/.zshrc, etc.):"
    echo ""
    echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo ""
fi

# Check optional tools
echo ""
echo "=== Optional Tools ==="
if command -v claude &> /dev/null; then
    echo "  Claude CLI: found (ar query will use LLM-powered Q&A)"
else
    echo "  Claude CLI: not found (ar query --context-only still works)"
fi

if command -v curl &> /dev/null; then
    echo "  curl: found (ar ingest --url will work)"
else
    echo "  curl: not found (URL ingestion disabled)"
fi

if [ -d "/Applications/Obsidian.app" ] || command -v obsidian &> /dev/null; then
    echo "  Obsidian: found (open wiki/ folders as vaults for visual browsing)"
else
    echo "  Obsidian: not found (optional — wiki works without it)"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Quick start:"
echo "  ar ingest --agent ${AGENTS%% *} --text \"Your first insight\" --topic \"research\""
echo "  ar compile --agent ${AGENTS%% *} --full"
echo "  ar search --agent ${AGENTS%% *} \"research\""
echo ""
echo "Full docs: README.md"
