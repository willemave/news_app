#!/usr/bin/env bash
set -euo pipefail

# Smoke test helper for iOS simulator + axe CLI.
#
# Usage:
#   scripts/axe_simulator_smoke.sh
#   scripts/axe_simulator_smoke.sh --udid <SIM_UDID> --bundle-id org.willemaw.newsly
#   scripts/axe_simulator_smoke.sh --record-video --capture-logs
#
# Environment overrides:
#   OUTPUT_DIR=/tmp/axe_newsly_smoke
#   BUILD_BEFORE_RUN=1
#   XCODE_PROJECT=client/newsly/newsly.xcodeproj
#   XCODE_SCHEME=newsly

BUNDLE_ID="org.willemaw.newsly"
UDID=""
OUTPUT_DIR="${OUTPUT_DIR:-/tmp/axe_newsly_smoke_$(date +%Y%m%d_%H%M%S)}"
BUILD_BEFORE_RUN="${BUILD_BEFORE_RUN:-0}"
XCODE_PROJECT="${XCODE_PROJECT:-client/newsly/newsly.xcodeproj}"
XCODE_SCHEME="${XCODE_SCHEME:-newsly}"
APP_BUNDLE_PATH="${APP_BUNDLE_PATH:-/tmp/newsly_codex_build/Build/Products/Debug-iphonesimulator/newsly.app}"
INSTALL_APP="${INSTALL_APP:-1}"
RECORD_VIDEO=0
CAPTURE_LOGS=0

usage() {
  cat <<'EOF'
Usage: scripts/axe_simulator_smoke.sh [options]

Options:
  --udid <SIM_UDID>       Simulator UDID. If omitted, auto-selects booted sim.
  --bundle-id <BUNDLE_ID> App bundle id (default: org.willemaw.newsly).
  --output-dir <DIR>      Output folder for artifacts.
  --build                 Build app before launch.
  --no-install            Skip simulator app install before launch.
  --app-path <PATH>       App bundle path to install (default: /tmp/newsly_codex_build/.../newsly.app).
  --record-video          Record simulator video during smoke run.
  --capture-logs          Capture simulator logs during smoke run.
  -h, --help              Show this help.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --udid)
      UDID="${2:-}"
      shift 2
      ;;
    --bundle-id)
      BUNDLE_ID="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --build)
      BUILD_BEFORE_RUN=1
      shift
      ;;
    --no-install)
      INSTALL_APP=0
      shift
      ;;
    --app-path)
      APP_BUNDLE_PATH="${2:-}"
      shift 2
      ;;
    --record-video)
      RECORD_VIDEO=1
      shift
      ;;
    --capture-logs)
      CAPTURE_LOGS=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

require_cmd axe
require_cmd xcrun

if [[ -z "$UDID" ]]; then
  UDID="$(axe list-simulators | awk -F '|' '$3 ~ /Booted/ {gsub(/^[[:space:]]+|[[:space:]]+$/, "", $1); print $1; exit}')"
fi

if [[ -z "$UDID" ]]; then
  echo "No booted simulator found. Boot one first, or pass --udid." >&2
  exit 1
fi

mkdir -p "$OUTPUT_DIR"
echo "Using simulator: $UDID"
echo "Output dir: $OUTPUT_DIR"

if [[ "$BUILD_BEFORE_RUN" == "1" ]]; then
  echo "Building app..."
  xcodebuild \
    -project "$XCODE_PROJECT" \
    -scheme "$XCODE_SCHEME" \
    -sdk iphonesimulator \
    -configuration Debug \
    -derivedDataPath /tmp/newsly_codex_build \
    build >/dev/null
fi

echo "Ensuring simulator is booted..."
xcrun simctl bootstatus "$UDID" -b >/dev/null

if [[ "$INSTALL_APP" == "1" ]]; then
  if [[ -d "$APP_BUNDLE_PATH" ]]; then
    echo "Installing app bundle: $APP_BUNDLE_PATH"
    xcrun simctl install "$UDID" "$APP_BUNDLE_PATH" >/dev/null
  else
    echo "Skipping install; app bundle not found at $APP_BUNDLE_PATH"
  fi
fi

LOG_PID=""
if [[ "$CAPTURE_LOGS" == "1" ]]; then
  echo "Starting simulator log capture..."
  xcrun simctl spawn "$UDID" log stream --style compact \
    --predicate "processImagePath CONTAINS 'newsly'" \
    > "$OUTPUT_DIR/sim_logs.txt" 2>&1 &
  LOG_PID="$!"
fi

VIDEO_PID=""
if [[ "$RECORD_VIDEO" == "1" ]]; then
  echo "Starting video recording..."
  axe record-video --udid "$UDID" --output "$OUTPUT_DIR/smoke.mp4" >/dev/null 2>&1 &
  VIDEO_PID="$!"
fi

cleanup() {
  if [[ -n "$VIDEO_PID" ]]; then
    kill "$VIDEO_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "$LOG_PID" ]]; then
    kill "$LOG_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

echo "Launching app: $BUNDLE_ID"
xcrun simctl launch "$UDID" "$BUNDLE_ID" >/dev/null || true
sleep 1

echo "Capturing launch artifacts..."
axe describe-ui --udid "$UDID" > "$OUTPUT_DIR/00_launch_ui.json"
axe screenshot --udid "$UDID" --output "$OUTPUT_DIR/00_launch.png" >/dev/null

echo "Navigating to Knowledge tab..."
if ! axe tap --id "tab.knowledge" --udid "$UDID" >/dev/null 2>&1; then
  # Coordinate fallback tuned for iPhone 17 Pro portrait.
  axe tap -x 265 -y 818 --udid "$UDID" >/dev/null 2>&1 || true
fi
sleep 1
axe describe-ui --udid "$UDID" > "$OUTPUT_DIR/01_knowledge_ui.json"
axe screenshot --udid "$UDID" --output "$OUTPUT_DIR/01_knowledge.png" >/dev/null

echo "Navigating to Live segment..."
LIVE_TAP_X=320
LIVE_TAP_Y=85
picker_frame="$(jq -r '..|objects|select(.AXUniqueId=="knowledge.tab_picker")|"\(.frame.x) \(.frame.y) \(.frame.width) \(.frame.height)"' "$OUTPUT_DIR/01_knowledge_ui.json" | head -n 1)"
if [[ -n "$picker_frame" ]]; then
  read -r picker_x picker_y picker_w picker_h <<<"$picker_frame"
  LIVE_TAP_X="$(awk "BEGIN {printf \"%.0f\", $picker_x + ($picker_w * 0.84)}")"
  LIVE_TAP_Y="$(awk "BEGIN {printf \"%.0f\", $picker_y + ($picker_h / 2)}")"
fi
axe tap -x "$LIVE_TAP_X" -y "$LIVE_TAP_Y" --udid "$UDID" >/dev/null 2>&1 || true
sleep 1
axe describe-ui --udid "$UDID" > "$OUTPUT_DIR/02_live_ui.json"
axe screenshot --udid "$UDID" --output "$OUTPUT_DIR/02_live.png" >/dev/null

echo "Connecting live session..."
if ! axe tap --id "live.connect" --udid "$UDID" >/dev/null 2>&1; then
  if ! axe tap --label "Connect" --udid "$UDID" >/dev/null 2>&1; then
    axe tap --id "live.controls" --udid "$UDID" >/dev/null 2>&1 || true
  fi
fi
sleep 2
axe describe-ui --udid "$UDID" > "$OUTPUT_DIR/03_connected_ui.json"
axe screenshot --udid "$UDID" --output "$OUTPUT_DIR/03_connected.png" >/dev/null

if jq -e '..|objects|select(.AXUniqueId=="live.status")' "$OUTPUT_DIR/03_connected_ui.json" >/dev/null 2>&1; then
  echo "Live UI identifiers detected (live.status present)."
else
  echo "Warning: live.status identifier not found; inspect artifacts."
fi

echo "Done. Artifacts written to:"
echo "  $OUTPUT_DIR"
ls -1 "$OUTPUT_DIR" | sed 's/^/  - /'
