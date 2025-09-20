#!/usr/bin/env bash
set -euo pipefail

# Ensure we have a writable HOME; service accounts may lack one
ORIG_HOME="${HOME:-}"
if [ -z "${HOME:-}" ] || [ ! -d "${HOME}" ] || [ ! -w "${HOME}" ]; then
  export HOME="${PWD}/.service_home"
  mkdir -p "${HOME}"
fi

# Provide standard directories for uv when HOME is synthetic
export XDG_DATA_HOME="${HOME}/.local/share"
export XDG_CACHE_HOME="${HOME}/.cache"
export PATH="${HOME}/.local/bin:${PATH}"

APT_CMD="apt-get"
if ! command -v apt-get >/dev/null 2>&1; then
  echo "apt-get not found; ensure required packages exist" >&2
  APT_CMD=""
fi

SUDO=""
if [ "$(id -u)" -ne 0 ] && command -v sudo >/dev/null 2>&1; then
  SUDO="sudo"
fi

if ! command -v curl >/dev/null 2>&1; then
  if [ -z "${APT_CMD}" ]; then
    echo "curl not installed and apt-get unavailable; install curl manually" >&2
    exit 1
  fi
  if [ "$(id -u)" -ne 0 ] && [ -z "${SUDO}" ]; then
    echo "curl not installed; re-run as root or with sudo privileges" >&2
    exit 1
  fi
  ${SUDO} ${APT_CMD} update
  ${SUDO} ${APT_CMD} install -y curl ca-certificates
fi

if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv installation failed or is not on PATH" >&2
  exit 1
fi

DESIRED_PYTHON="3.13"
uv python install "${DESIRED_PYTHON}"
uv sync

if [ -d .venv ]; then
  OWNER_USER="${SUDO_USER:-$(whoami)}"
  OWNER_GROUP="$(id -gn "$OWNER_USER")"
  chown -R "$OWNER_USER":"$OWNER_GROUP" .venv
fi

echo
cat <<MSG
Environment ready for $(whoami).
Activate it with:
  source .venv/bin/activate
MSG
