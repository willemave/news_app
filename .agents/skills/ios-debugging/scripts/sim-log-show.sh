#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 3 ]]; then
  echo "usage: $0 <predicate> [last-window] [device]" >&2
  echo "example: $0 'subsystem == \"org.willemaw.newsly\"' 5m booted" >&2
  exit 1
fi

predicate="$1"
last_window="${2:-5m}"
device="${3:-booted}"

exec xcrun simctl spawn "$device" log show \
  --style compact \
  --last "$last_window" \
  --predicate "$predicate" \
  --info --debug
