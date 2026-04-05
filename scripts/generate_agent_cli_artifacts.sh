#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AGENT_OPENAPI_OUTPUT="${AGENT_OPENAPI_OUTPUT:-$REPO_ROOT/cli/openapi/agent-openapi.json}"
GO_TARGET_DIR="${GO_TARGET_DIR:-$REPO_ROOT/cli/internal/api}"

cd "$REPO_ROOT"

PYTHONPATH="$REPO_ROOT" uv run python "$REPO_ROOT/scripts/export_agent_openapi_schema.py" \
  --output "$AGENT_OPENAPI_OUTPUT"

cd "$REPO_ROOT/cli"
go run github.com/ogen-go/ogen/cmd/ogen@v1.20.1 \
  --clean \
  --target "$GO_TARGET_DIR" \
  --package api \
  "$AGENT_OPENAPI_OUTPUT"

gofmt -w "$GO_TARGET_DIR"
