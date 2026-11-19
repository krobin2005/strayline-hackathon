#!/bin/bash
# Strayline Desk: one-click start for the live demo. Double-click in Finder, or run ./start_demo.command
#
# Does, in order: checks Wi-Fi and memory-hungry apps, starts Ollama, builds the logs demo file if it's
# missing, starts the app offline, waits until both models are loaded, then opens Safari and the demo files.
# Leave the Terminal window open during the demo. Press Ctrl+C (or close the window) to stop the app.
# PORT=8002 ./start_demo.command uses another port; DEMO_SELFTEST=1 stops the app again once it's ready.

cd "$(dirname "$0")" || exit 1
PORT="${PORT:-8000}"
URL="http://localhost:$PORT"
LOG="data/demo/app.log"
FILES="$HOME/Desktop/Strayline Demo Files"
GENERAL="gemma4:e4b-it-q4_K_M"
VISION="qwen3-vl:8b"

say_step() { printf "\n\033[1m%s\033[0m\n" "$1"; }
ok() { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$1"; }

say_step "1. Network and memory"
if [ "$(networksetup -getairportpower en0 2>/dev/null | awk '{print $NF}')" = "On" ]; then
  warn "Wi-Fi is on. Turn it off to show the demo runs offline (the app doesn't need it)."
else
  ok "Wi-Fi is off"
fi
heavy=""
for app in "Google Chrome" "ChatGPT" "Claude" "Codex" "Slack" "Microsoft Teams" "Spotify" "Docker"; do
  pgrep -xq "$app" && heavy="$heavy, $app"
done
if [ -n "$heavy" ]; then
  warn "Still open: ${heavy#, }. Quit them so both models fit in memory (otherwise switching inputs reloads a model)."
else
  ok "No memory-hungry apps open"
fi

say_step "2. Ollama"
if ! curl -s -m 2 localhost:11434/api/version >/dev/null; then
  open -a Ollama
  for _ in $(seq 1 30); do curl -s -m 2 localhost:11434/api/version >/dev/null && break; sleep 1; done
fi
if curl -s -m 2 localhost:11434/api/version >/dev/null; then ok "Ollama is running"; else fail "Ollama didn't start. Open the Ollama app, then run this again."; exit 1; fi

say_step "3. Demo files"
if [ ! -f data/demo/campus_afternoon.csv ]; then
  .venv/bin/python tests/make_demo_intrusions.py >/dev/null && ok "Built data/demo/campus_afternoon.csv" \
    || warn "Couldn't build the logs file (needs data/raw/wednesday.csv). The other inputs still work."
else
  ok "Logs file ready"
fi

say_step "4. Strayline app on port $PORT"
APP_PID=""
cleanup() {
  if [ -n "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
    printf "\nStopping Strayline Desk…\n"; kill "$APP_PID" 2>/dev/null; wait "$APP_PID" 2>/dev/null
  fi
}
trap cleanup EXIT
trap 'exit 0' INT TERM HUP

if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  holder=$(lsof -tiTCP:"$PORT" -sTCP:LISTEN | head -1)
  fail "Port $PORT is already in use by process $holder, started $(ps -o lstart= -p "$holder")."
  echo "    If that's an old Strayline window, close it (or run: kill $holder), then run this again."
  exit 1
fi
mkdir -p data/demo
HF_HUB_OFFLINE=1 PORT="$PORT" .venv/bin/python -m desk >"$LOG" 2>&1 &
APP_PID=$!
for _ in $(seq 1 60); do curl -s -m 2 "$URL/api/health" >/dev/null && break; sleep 1; done
if curl -s -m 2 "$URL/api/health" >/dev/null; then ok "App is up (log: $LOG)"; else fail "App didn't start. See $LOG"; exit 1; fi

say_step "5. Loading both models (about a minute)"
loaded() { curl -s -m 3 localhost:11434/api/ps | grep -oE "\"name\": ?\"($GENERAL|$VISION)\"" | wc -l | tr -d ' '; }
for _ in $(seq 1 90); do [ "$(loaded)" -ge 2 ] && break; sleep 2; done
if [ "$(loaded)" -lt 2 ]; then
  # The app's own warm-up may have finished with one model evicted; warm again in the order that keeps both.
  .venv/bin/python -c "import sys; sys.path.insert(0, '.'); from desk import llm; llm.warm_up()"
fi
if [ "$(loaded)" -ge 2 ]; then
  ok "Both models loaded: $GENERAL and $VISION"
else
  warn "Only one model fits in memory right now. Quit the apps listed above and run this again,"
  warn "or keep video and image questions together, then audio, document, code and logs."
fi

say_step "6. Opening Safari and the demo files"
if [ -n "$DEMO_SELFTEST" ]; then
  ok "Self-test finished; not opening windows"
  exit 0
fi
open -a Safari "$URL"
if [ -d "$FILES" ]; then open "$FILES"; else open demo data/demo; fi

printf "\n\033[1;32mReady.\033[0m  %s is open in Safari. Drag files from the Finder window.\n" "$URL"
printf "Keep this window open during the demo. Press Ctrl+C or close it to stop the app.\n\n"
wait "$APP_PID"
