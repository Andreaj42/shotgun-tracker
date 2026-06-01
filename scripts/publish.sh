#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python scripts/export_latest.py
python scripts/export_history.py

git add docs/data/latest.json docs/data/history.json

if git diff --cached --quiet; then
  echo "No data changes to publish."
  exit 0
fi

git commit -m "Update Shotgun data"
git push