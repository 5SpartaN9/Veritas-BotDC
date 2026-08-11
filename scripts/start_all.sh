#!/usr/bin/env bash
set -euo pipefail

# Start Discord bot in background, then the web panel (same disk / DATA_DIR).
python bot.py &
BOT_PID=$!

cleanup() {
  kill "$BOT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

uvicorn web.app:app --host 0.0.0.0 --port "${PORT:-8000}"
