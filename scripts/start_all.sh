#!/usr/bin/env bash
set -eu

# Start Discord bot in background, then keep the web panel in foreground.
python bot.py &
BOT_PID=$!

cleanup() {
  kill "$BOT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

exec uvicorn web.app:app --host 0.0.0.0 --port "${PORT:-8000}"