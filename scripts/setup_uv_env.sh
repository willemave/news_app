#!/usr/bin/env bash
set -euo pipefail

# Bootstrap/refresh the uv-based Python environment for the app.
# Intended to be run as the service user (newsapp) on the deployment host.

EXPECTED_USER="${ENV_USER:-newsapp}"

if [[ "${FORCE_RUN_OUTSIDE_USER:-false}" != "true" && "$(id -un)" != "$EXPECTED_USER" ]]; then
  echo "ERROR: run this script as $EXPECTED_USER (current user: $(id -un))." >&2
  exit 1
fi

PYTHON_VERSION="3.13"
LOCK_STRATEGY="auto"  # auto = frozen if uv.lock exists

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python-version)
      PYTHON_VERSION="$2"
      shift 2
      ;;
    --sync-frozen)
      LOCK_STRATEGY="frozen"
      shift
      ;;
    --sync-thawed)
      LOCK_STRATEGY="thawed"
      shift
      ;;
    --force)
      FORCE_RUN_OUTSIDE_USER="true"
      shift
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/setup_uv_env.sh [--python-version X.Y] [--sync-frozen|--sync-thawed]

Installs/updates uv via pipx, ensures the requested Python runtime is available,
re-creates the .venv, and runs uv sync (frozen if uv.lock present by default).
USAGE
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# Resolve project root relative to this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

echo "[setup] Running as $(whoami) in $PROJECT_ROOT"

export PATH="$HOME/.local/bin:$PATH"

if ! command -v pipx >/dev/null 2>&1; then
  echo "[setup] pipx not found; installing via python3 -m pip --user"
  python3 -m pip install --user pipx
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "[setup] Ensuring uv is installed via pipx"
pipx install uv --force

echo "[setup] Installing Python $PYTHON_VERSION via uv"
uv python install "$PYTHON_VERSION"

VENV_PATH="$PROJECT_ROOT/.venv"
VENV_PY_BIN="$VENV_PATH/bin/python"
NEEDS_VENV_REBUILD=false
CURRENT_VENV_VERSION=""

if [[ ! -d "$VENV_PATH" ]]; then
  echo "[setup] No existing virtualenv detected; will create .venv"
  NEEDS_VENV_REBUILD=true
elif [[ ! -x "$VENV_PY_BIN" ]]; then
  echo "[setup] Existing .venv is missing Python executable; will recreate"
  NEEDS_VENV_REBUILD=true
else
  CURRENT_VENV_VERSION="$($VENV_PY_BIN -c 'import sys; print(sys.version.split()[0])')"
  if "$VENV_PY_BIN" - "$PYTHON_VERSION" <<'PY'
import sys
desired = sys.argv[1]
current = sys.version.split()[0]
def normalize(value):
    parts = value.split('.')
    while parts and parts[-1] == '':
        parts.pop()
    return parts
desired_parts = normalize(desired)
current_parts = normalize(current)
length = min(len(desired_parts), len(current_parts))
if desired_parts[:length] == current_parts[:length]:
    sys.exit(0)
sys.exit(1)
PY
  then
    :
  else
    echo "[setup] Existing virtualenv uses Python $CURRENT_VENV_VERSION; target is $PYTHON_VERSION. Recreating .venv"
    NEEDS_VENV_REBUILD=true
  fi
fi

if "$NEEDS_VENV_REBUILD"; then
  echo "[setup] Creating virtual environment with Python $PYTHON_VERSION"
  uv venv --clear --python "$PYTHON_VERSION" "$VENV_PATH"
  CURRENT_VENV_VERSION="$($VENV_PY_BIN -c 'import sys; print(sys.version.split()[0])')"
else
  echo "[setup] Reusing existing virtualenv (.venv) with Python ${CURRENT_VENV_VERSION:-unknown}"
fi

echo "[setup] Activating venv and syncing dependencies"
source "$VENV_PATH/bin/activate"

SYNC_ARGS=(sync)
case "$LOCK_STRATEGY" in
  frozen)
    SYNC_ARGS+=(--frozen)
    ;;
  thawed)
    :
    ;;
  auto)
    if [[ -f uv.lock ]]; then
      SYNC_ARGS+=(--frozen)
    fi
    ;;
esac

uv "${SYNC_ARGS[@]}"

if [[ -x .venv/bin/playwright ]]; then
  echo "[setup] Installing Playwright browsers (chromium)"
  .venv/bin/playwright install chromium
else
  echo "[setup] Playwright CLI not found in .venv; skipping browser install" >&2
fi

echo "[setup] uv environment ready"
