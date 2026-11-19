#!/bin/sh
# Strayline Desk: one-time setup on a new laptop (macOS or Linux). Safe to run again.
#   sh setup.sh
# Needs: Python 3.11+, Ollama (https://ollama.com/download), ~14 GB free disk, internet (this once).
set -e
cd "$(dirname "$0")"

say() { printf '\n==> %s\n' "$1"; }
VISION_MODEL="${DESK_VISION_MODEL:-qwen3-vl:8b}"
GENERAL_MODEL="${DESK_GENERAL_MODEL:-gemma4:e4b-it-q4_K_M}"

say "Checking Python"
PY=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then
    PY="$candidate"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.11 or newer is needed. Install it from https://www.python.org/downloads/ and run this again."
  exit 1
fi
"$PY" --version

say "Creating .venv and installing packages"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
echo "packages ok"

say "Checking Ollama"
OLLAMA="$(command -v ollama || true)"
[ -z "$OLLAMA" ] && [ -x /Applications/Ollama.app/Contents/Resources/ollama ] && OLLAMA=/Applications/Ollama.app/Contents/Resources/ollama
if [ -z "$OLLAMA" ]; then
  echo "Ollama isn't installed. Download it from https://ollama.com/download (on a Mac: unzip it, drag"
  echo "Ollama.app to Applications and open it once), then run: sh setup.sh"
  exit 1
fi
if ! curl -s http://localhost:11434/api/version >/dev/null 2>&1; then
  echo "Starting Ollama…"
  if [ -d /Applications/Ollama.app ]; then open -a /Applications/Ollama.app; else ("$OLLAMA" serve >/dev/null 2>&1 &); fi
  i=0; until curl -s http://localhost:11434/api/version >/dev/null 2>&1; do i=$((i+1)); [ $i -gt 30 ] && { echo "Ollama didn't start."; exit 1; }; sleep 1; done
fi
curl -s http://localhost:11434/api/version; echo

say "Downloading the two models (about 13 GB the first time; skipped if already here)"
"$OLLAMA" pull "$VISION_MODEL"
"$OLLAMA" pull "$GENERAL_MODEL"

say "Downloading the sound classifier (~350 MB, once)"
.venv/bin/python -c "from desk.handlers import audio; audio.classifier(); print('sound classifier ok')"

say "Quick check"
.venv/bin/python - <<'EOF'
from desk import llm
answer, seconds = llm.chat(llm.GENERAL_MODEL, "Reply with exactly: ready")
print(f"{llm.GENERAL_MODEL}: {answer!r} in {seconds:.1f}s")
EOF

if [ -f data/raw/monday.csv ] && [ ! -f data/models/detector.joblib ]; then
  say "Training the Strayline log detector on CIC-IDS2017 (about 15 s)"
  .venv/bin/python -m desk.detector train
fi

say "Done. Start the app with:  .venv/bin/python -m desk"
echo "Then open http://localhost:8000 (the app also prints an address for phones on the same Wi-Fi)."
echo "Optional: put the organizers' practice pack in data/practice/ and run  .venv/bin/python -m desk.eval"
