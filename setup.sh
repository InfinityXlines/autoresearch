#!/usr/bin/env bash
set -euo pipefail

echo "=== Autoresearch Setup ==="

# Create system directories
mkdir -p ~/.autoresearch/agents/{jade,katana,magdalena}

# Create agent subdirs
for agent in jade katana magdalena; do
    for subdir in raw raw/.quarantine wiki/topics wiki/assets outputs; do
        mkdir -p ~/.autoresearch/agents/$agent/$subdir
    done
done

# Create shared wiki
mkdir -p ~/shared-memory/wiki/topics

# Copy config if not exists
if [ ! -f ~/.autoresearch/config.yaml ]; then
    cp "$(dirname "$0")/templates/config.yaml" ~/.autoresearch/config.yaml
    echo "Created ~/.autoresearch/config.yaml"
fi

# Make ar executable and symlink
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
chmod +x "$SCRIPT_DIR/ar"

# Symlink to local bin
mkdir -p ~/.local/bin
ln -sf "$SCRIPT_DIR/ar" ~/.local/bin/ar
echo "Symlinked ar -> ~/.local/bin/ar"

echo "=== Setup complete ==="
echo "Run: ar --help for usage"
