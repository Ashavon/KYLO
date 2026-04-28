#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Find drive root (walk up until _DRIVE_HOME found)
DRIVE_ROOT="$SCRIPT_DIR"
while [ ! -f "$DRIVE_ROOT/_DRIVE_HOME" ] && [ "$DRIVE_ROOT" != "/" ]; do
  DRIVE_ROOT="$(dirname "$DRIVE_ROOT")"
done
ENV_DIR="$DRIVE_ROOT/_env"

echo "╔══════════════════════════════╗"
echo "║     KYLO File Explorer       ║"
echo "╚══════════════════════════════╝"
echo "Drive root: $DRIVE_ROOT"

# Python check
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 not found. Install from https://python.org"; exit 1
fi

# Create venv if missing
if [ ! -d "$ENV_DIR" ]; then
  echo "⚙️  First run: creating Python environment at _env/ ..."
  python3 -m venv "$ENV_DIR"
fi

# Activate and install/upgrade deps
source "$ENV_DIR/bin/activate"
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet --upgrade

# Ollama check
if ! curl -s http://localhost:11434 >/dev/null 2>&1; then
  echo "⚠️  Ollama not running. AI features disabled."
  echo "    → Install: https://ollama.com"
  echo "    → Then run: ollama pull gemma3:4b && ollama pull nomic-embed-text"
  export KYLO_AI_AVAILABLE=false
else
  export KYLO_AI_AVAILABLE=true
fi

# Set drive-relative config path
export KYLO_DRIVE_ROOT="$DRIVE_ROOT"

# Launch
python3 "$SCRIPT_DIR/backend/main.py" &
SERVER_PID=$!
sleep 2
open http://localhost:8765 2>/dev/null || xdg-open http://localhost:8765 2>/dev/null
echo "✅ KYLO running at http://localhost:8765  (PID $SERVER_PID)"
echo "   Press Ctrl+C to stop."
wait $SERVER_PID
