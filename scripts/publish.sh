#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

BRANCH="${PUBLISH_BRANCH:-main}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

"$PYTHON_BIN" scripts/export_latest.py
"$PYTHON_BIN" scripts/export_history.py

git add docs/data/latest.json docs/data/history.json

if git diff --cached --quiet; then
  echo "No data changes to publish."
  exit 0
fi

git commit -m "Update Shotgun data"
git pull --rebase origin "$BRANCH"
git push origin "HEAD:$BRANCH"
