#!/usr/bin/env bash
# Run the app in the foreground (development). Ctrl-C to stop.
set -euo pipefail
cd "$(dirname "$0")/.."
exec .venv/bin/python -m uvicorn app.main:app --host "${APP_HOST:-127.0.0.1}" --port "${APP_PORT:-8765}" --reload
