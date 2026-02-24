#!/usr/bin/env bash
# Generate local .env files from .env.example templates.
# Safe to run repeatedly — never overwrites existing .env files.
# Usage: ./scripts/init_env.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

copy_if_missing() {
  local src="$1" dst="$2"
  if [ -f "$dst" ]; then
    echo "  [SKIP] $dst already exists"
  elif [ ! -f "$src" ]; then
    echo "  [WARN] Template $src not found"
  else
    cp "$src" "$dst"
    echo "  [CREATED] $dst from $src"
  fi
}

echo "=== ArchScan: Initialize local .env files ==="
copy_if_missing "$ROOT/.env.example"          "$ROOT/.env"
copy_if_missing "$ROOT/frontend/.env.example" "$ROOT/frontend/.env"
echo ""
echo "Done. Edit .env files with your local settings."
echo "NEVER commit .env files — only .env.example templates are tracked."
