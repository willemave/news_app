#!/bin/bash
# Run the queue watchdog loop every 5 minutes.

set -euo pipefail

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

cd "$PROJECT_ROOT"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
fi

if [ ! -f ".env" ]; then
  echo "ERROR: .env file not found at $PROJECT_ROOT/.env" >&2
  exit 1
fi

exec python scripts/watchdog_queue_recovery.py --loop --interval-seconds 300
