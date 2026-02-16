#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT_DIR"

OUTPUT_DIR="${OUTPUT_DIR:-/tmp/live_tab_debug_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$OUTPUT_DIR"

echo "== Live Tab Local Debug =="
echo "repo: $ROOT_DIR"
echo "artifacts: $OUTPUT_DIR"

if ! command -v axe >/dev/null 2>&1; then
  echo "ERROR: 'axe' CLI not found in PATH."
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: 'uv' not found in PATH."
  exit 1
fi

if ! curl -fsS http://127.0.0.1:8000/health >/dev/null; then
  echo "ERROR: backend is not reachable at http://127.0.0.1:8000"
  echo "Start server first, e.g. scripts/start_server.sh"
  exit 1
fi

if [[ -z "${ELEVENLABS_API_KEY:-}" ]]; then
  echo "WARN: ELEVENLABS_API_KEY is not set in this shell."
  echo "      voice_tools_e2e.py may fail if server environment is also missing it."
fi

echo
echo "[1/2] Running ElevenLabs + tools e2e check..."
uv run python scripts/voice_tools_e2e.py | tee "$OUTPUT_DIR/voice_tools_e2e.txt"

echo
echo "[2/2] Running axe simulator live-tab smoke..."
scripts/axe_simulator_smoke.sh \
  --capture-logs \
  --output-dir "$OUTPUT_DIR/axe" | tee "$OUTPUT_DIR/axe_smoke.txt"

echo
echo "Done. Key artifacts:"
echo "  - $OUTPUT_DIR/voice_tools_e2e.txt"
echo "  - $OUTPUT_DIR/axe_smoke.txt"
echo "  - $OUTPUT_DIR/axe/"
