#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

PYTHONPATH="$REPO_ROOT" uv run python scripts/export_openapi_schema.py
PYTHONPATH="$REPO_ROOT" uv run python scripts/generate_ios_contracts.py
"$REPO_ROOT/scripts/generate_ios_openapi_artifacts.sh"

echo "Regenerated OpenAPI + Swift API contracts."
