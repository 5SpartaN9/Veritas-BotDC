#!/usr/bin/env bash
set -u

# Keep the web panel up even if the Discord bot crashes.
python bot.py &
BOT_PID=$!

cleanup() {
  kill "$BOT_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Give the bot a moment; do not fail the whole service if it dies.
sleep 2
if ! kill -0 "$BOT_PID" 2>/dev/null; then
  echo "WARNING: Discord bot exited early; starting web panel anyway."
fi

exec uvicorn web.app:app --host 0.0.0.0 --port "${PORT:-8000}"
