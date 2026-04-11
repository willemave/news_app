#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 <predicate> <output-file> [device]" >&2
  echo "example: $0 'subsystem == \"org.willemaw.newsly\"' /tmp/newsly.log booted" >&2
  exit 1
fi

predicate="$1"
output_file="$2"
device="${3:-booted}"

mkdir -p "$(dirname "$output_file")"

exec xcrun simctl spawn "$device" log stream \
  --style compact \
  --level debug \
  --predicate "$predicate" | tee "$output_file"
