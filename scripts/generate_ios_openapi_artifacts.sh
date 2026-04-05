#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GENERATOR_TAG="${SWIFT_OPENAPI_GENERATOR_GIT_TAG:-1.10.2}"
GENERATOR_REPO="${SWIFT_OPENAPI_GENERATOR_GIT_URL:-https://github.com/apple/swift-openapi-generator}"
GENERATOR_CLONE_DIR="${SWIFT_OPENAPI_GENERATOR_CLONE_DIR:-$REPO_ROOT/.tmp/swift-openapi-generator}"
GENERATOR_BUILD_CONFIGURATION="${SWIFT_OPENAPI_GENERATOR_BUILD_CONFIGURATION:-debug}"
OPENAPI_PATH="${OPENAPI_PATH:-$REPO_ROOT/docs/library/reference/openapi.json}"
CONFIG_PATH="${CONFIG_PATH:-$REPO_ROOT/client/newsly/openapi-generator-config.yaml}"
OUTPUT_DIRECTORY="${OUTPUT_DIRECTORY:-$REPO_ROOT/client/newsly/OpenAPI/Generated}"
GENERATOR_BIN="$GENERATOR_CLONE_DIR/.build/$GENERATOR_BUILD_CONFIGURATION/swift-openapi-generator"

mkdir -p "$REPO_ROOT/.tmp"

if [[ ! -d "$GENERATOR_CLONE_DIR/.git" ]]; then
  rm -rf "$GENERATOR_CLONE_DIR"
  git \
    -c advice.detachedHead=false \
    clone \
    --branch "$GENERATOR_TAG" \
    --depth 1 \
    "$GENERATOR_REPO" \
    "$GENERATOR_CLONE_DIR"
fi

swift \
  build \
  --package-path "$GENERATOR_CLONE_DIR" \
  --configuration "$GENERATOR_BUILD_CONFIGURATION" \
  --product swift-openapi-generator \
  >/dev/null

mkdir -p "$OUTPUT_DIRECTORY"

"$GENERATOR_BIN" generate \
  --config "$CONFIG_PATH" \
  --output-directory "$OUTPUT_DIRECTORY" \
  "$OPENAPI_PATH"

echo "Generated Swift OpenAPI artifacts in $OUTPUT_DIRECTORY"
