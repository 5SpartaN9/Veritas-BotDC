#!/usr/bin/env bash
set -u

# Panel first — users must reach the dashboard even if the Discord bot dies.
python -m uvicorn web.app:app --host 0.0.0.0 --port "${PORT:-8000}" &
WEB_PID=$!

BOT_PID=""

cleanup() {
  if [[ -n "${BOT_PID}" ]]; then
    kill "$BOT_PID" 2>/dev/null || true
  fi
  kill "$WEB_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Give the web process a moment to bind the port.
sleep 1
if ! kill -0 "$WEB_PID" 2>/dev/null; then
  echo "ERROR: web panel failed to start"
  wait "$WEB_PID"
  exit $?
fi

# Restart the bot in a loop without taking down the panel.
(
  while true; do
    echo "Starting Discord bot..."
    python bot.py
    code=$?
    echo "WARNING: Discord bot exited with code ${code}; restarting in 8s"
    sleep 8
  done
) &
BOT_PID=$!

# Keep the container alive as long as the web panel is up.
wait "$WEB_PID"
exit $?
