#!/usr/bin/env bash
# One-command local run:  ./run.sh   -> http://localhost:8000
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
# Load local configuration for a native run, without printing secrets.
if [ -f "$ROOT/.env" ]; then
  set -a
  . "$ROOT/.env"
  set +a
fi
cd "$ROOT/backend"
[ -d ../.venv ] || { python3 -m venv ../.venv; ../.venv/bin/pip install -q -r requirements.txt; }
exec ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
