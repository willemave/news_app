#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PYTHON="${PYTHON:-$REPO_ROOT/.venv/bin/python}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

PYTHONPATH=. "$PYTHON" scripts/export_openapi_schema.py
PYTHONPATH=. "$PYTHON" scripts/generate_ios_contracts.py

echo "Regenerated OpenAPI + Swift API contracts."

