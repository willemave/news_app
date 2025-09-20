#!/usr/bin/env bash
set -euo pipefail

# Sync the entire app repo to a remote host and set ownership to newsapp.
# Safe by default: excludes caches/venvs/git/node_modules/dbs.
#
# Defaults:
#   Host: willem@192.3.250.10
#   Remote app dir: /opt/news_app
#   Owner: newsapp:newsapp
#   Remote staging: /tmp/news_app_sync
#
# Options:
#   -h, --host USER@HOST            SSH target (default: willem@192.3.250.10)
#   -d, --dir  /remote/path         Remote app dir (default: /opt/news_app)
#   -o, --owner user:group          chown target (default: newsapp:newsapp)
#       --staging /tmp/path         Remote staging dir (default: /tmp/news_app_sync)
#       --no-delete                 Do not delete remote files removed locally
#       --install                   Create/activate venv via uv and install deps
#       --python-version 3.13       Python version for uv venv (default: 3.13)
#       --force-env                 Force deletion/recreation of the remote .venv
#       --debug                     Verbose output; enable local and remote tracing
#       --restart-supervisor        Reread/update and restart programs
#       --programs "a b c"          Supervisor program names (default: news_app_server news_app_workers news_app_scrapers)
#       --promote-user USER         Run remote promote step as this user (default: root)
#       --extra-exclude PATTERN     Additional rsync exclude (can repeat)
#       --dry-run                   Show what would be done by rsync
#
# Example:
#   scripts/deploy/push_app.sh --install --restart-supervisor

REMOTE_HOST="willem@192.3.250.10"
REMOTE_DIR="/opt/news_app"
OWNER_GROUP="newsapp:newsapp"
REMOTE_STAGING="/tmp/news_app_sync"
RSYNC_DELETE=true
DO_INSTALL=false
PY_VER="3.13"
DEBUG=false
RESTART_SUP=false
PROGRAMS=(news_app_server news_app_workers news_app_scrapers)
DRY_RUN=false
PROMOTE_USER="root"
ENV_REFRESHED=false
FORCE_ENV=false
REMOVE_REMOTE_VENV_REASON=""

EXCLUDES=(
  ".git/"
  ".venv/"
  "env/"
  "node_modules/"
  "__pycache__/"
  ".ruff_cache/"
  ".pytest_cache/"
  ".benchmarks/"
  "*.pyc"
  "*.pyo"
  "*.db"
  "*.sqlite"
  ".DS_Store"
  "logs/"
  "ai-memory/"
  "data/"
  "archive/"
  "client/"   # iOS client not needed on server
  ".env"      # deploy uses .env.racknerd instead of local dev env
)

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--host) REMOTE_HOST="$2"; shift 2 ;;
    -d|--dir) REMOTE_DIR="$2"; shift 2 ;;
    -o|--owner) OWNER_GROUP="$2"; shift 2 ;;
    --staging) REMOTE_STAGING="$2"; shift 2 ;;
    --no-delete) RSYNC_DELETE=false; shift ;;
    --install) DO_INSTALL=true; shift ;;
    --python-version) PY_VER="$2"; shift 2 ;;
    --force-env) FORCE_ENV=true; shift ;;
    --debug) DEBUG=true; shift ;;
    --restart-supervisor) RESTART_SUP=true; shift ;;
    --programs) shift; IFS=' ' read -r -a PROGRAMS <<< "${1:-}"; shift || true ;;
    --promote-user) PROMOTE_USER="$2"; shift 2 ;;
    --extra-exclude) EXCLUDES+=("$2"); shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -\?|--help|-h)
      sed -n '1,80p' "$0" | sed -n '1,50p' | sed 's/^# \{0,1\}//' ; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# Resolve repo root (this script lives in scripts/deploy/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
REPO_ROOT="$( cd "$SCRIPT_DIR/../.." && pwd )"
cd "$REPO_ROOT"

LOCAL_UV_LOCK_HASH=""
if [[ -f "uv.lock" ]]; then
  LOCAL_UV_LOCK_HASH="$(sha256sum uv.lock | awk '{print $1}')"
fi

REMOTE_UV_LOCK_HASH=""
REMOTE_HASH_CMD_SUDO=$(printf "sudo -n sha256sum %q" "$REMOTE_DIR/uv.lock")
REMOTE_HASH_CMD=$(printf "sha256sum %q" "$REMOTE_DIR/uv.lock")
if REMOTE_HASH_OUTPUT=$(ssh "$REMOTE_HOST" "$REMOTE_HASH_CMD_SUDO" 2>/dev/null); then
  REMOTE_UV_LOCK_HASH="$(printf '%s' "$REMOTE_HASH_OUTPUT" | awk '{print $1}' | tr -d '\r')"
elif REMOTE_HASH_OUTPUT=$(ssh "$REMOTE_HOST" "$REMOTE_HASH_CMD" 2>/dev/null); then
  REMOTE_UV_LOCK_HASH="$(printf '%s' "$REMOTE_HASH_OUTPUT" | awk '{print $1}' | tr -d '\r')"
else
  REMOTE_UV_LOCK_HASH=""
fi

SHOULD_REMOVE_REMOTE_VENV=false
if [[ -n "$LOCAL_UV_LOCK_HASH" || -n "$REMOTE_UV_LOCK_HASH" ]]; then
  if [[ "$LOCAL_UV_LOCK_HASH" != "$REMOTE_UV_LOCK_HASH" ]]; then
    SHOULD_REMOVE_REMOTE_VENV=true
    REMOVE_REMOTE_VENV_REASON="uv.lock changed"
  fi
fi

if "$FORCE_ENV"; then
  if [[ -n "$REMOVE_REMOTE_VENV_REASON" ]]; then
    REMOVE_REMOTE_VENV_REASON="forced by --force-env; $REMOVE_REMOTE_VENV_REASON"
  else
    REMOVE_REMOTE_VENV_REASON="forced by --force-env"
  fi
  SHOULD_REMOVE_REMOTE_VENV=true
fi

if "$DEBUG"; then
  set -x
  echo "DEBUG: REMOTE_HOST=$REMOTE_HOST REMOTE_DIR=$REMOTE_DIR OWNER_GROUP=$OWNER_GROUP REMOTE_STAGING=$REMOTE_STAGING"
  echo "DEBUG: RSYNC_DELETE=$RSYNC_DELETE DO_INSTALL=$DO_INSTALL PY_VER=$PY_VER RESTART_SUP=$RESTART_SUP"
fi

if [[ "$OWNER_GROUP" == *:* ]]; then
  SERVICE_USER="${OWNER_GROUP%%:*}"
  SERVICE_GROUP="${OWNER_GROUP##*:}"
else
  SERVICE_USER="$OWNER_GROUP"
  SERVICE_GROUP="$OWNER_GROUP"
fi

if [[ -z "$SERVICE_USER" || -z "$SERVICE_GROUP" ]]; then
  echo "Unable to determine service user/group from owner group: $OWNER_GROUP" >&2
  exit 1
fi

echo "→ Preparing remote directories on $REMOTE_HOST"
# Staging can be created without sudo; app dir typically needs sudo
ssh "$REMOTE_HOST" "mkdir -p '$REMOTE_STAGING' && chmod 755 '$REMOTE_STAGING'" || true
ssh -tt "$REMOTE_HOST" "sudo mkdir -p '$REMOTE_DIR' && sudo chown '$OWNER_GROUP' '$REMOTE_DIR' && sudo chmod 755 '$REMOTE_DIR' && echo 'Remote app dir prepared: $REMOTE_DIR'"

echo "→ Rsync to staging: $REMOTE_HOST:$REMOTE_STAGING (delete=$RSYNC_DELETE)"

RSYNC_ARGS=(-az)
"$DRY_RUN" && RSYNC_ARGS+=(-n -v)
"$RSYNC_DELETE" && RSYNC_ARGS+=(--delete)

for pat in "${EXCLUDES[@]}"; do
  RSYNC_ARGS+=(--exclude "$pat")
done

# Trailing slash sends repo contents (not the top-level dir)
rsync "${RSYNC_ARGS[@]}" ./ "$REMOTE_HOST:$REMOTE_STAGING/"

echo "→ Promoting staging to app dir with proper ownership (rsync --chown)"
REMOTE_PROMOTE_SCRIPT="/tmp/news_app_promote.sh"
REMOTE_PROMOTE_USER="$PROMOTE_USER"

ssh "$REMOTE_HOST" "cat > '$REMOTE_PROMOTE_SCRIPT'" <<'REMOTE_SCRIPT'
#!/usr/bin/env bash
set -euo pipefail

REMOTE_STAGING="$1"
REMOTE_DIR="$2"
OWNER_GROUP="$3"
REMOTE_DELETE="${4:-true}"
REMOTE_DEBUG="${5:-false}"

if [[ "$REMOTE_DEBUG" == "true" ]]; then
  set -x
fi

echo "[remote] whoami: $(whoami)"
RSYNC_VERSION_LINE="$(rsync --version 2>/dev/null | head -n1 || true)"
if [[ -n "$RSYNC_VERSION_LINE" ]]; then
  echo "[remote] rsync: $RSYNC_VERSION_LINE"
else
  echo "[remote] rsync version check failed"
fi

if [[ ! -d "$REMOTE_STAGING" ]]; then
  echo "[remote] staging dir $REMOTE_STAGING missing; refusing to sync to avoid clearing $REMOTE_DIR" >&2
  exit 1
fi

if [[ -z "$(find "$REMOTE_STAGING" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
  echo "[remote] staging dir $REMOTE_STAGING is empty; refusing to sync to avoid clearing $REMOTE_DIR" >&2
  exit 1
fi

RSYNC_OPTS=(-a)
if [[ "$REMOTE_DELETE" == "true" ]]; then
  RSYNC_OPTS+=(--delete)
else
  echo "[remote] remote delete disabled (sync may leave old files)"
fi

if [[ $(id -u) -eq 0 ]]; then
  RSYNC_OPTS+=(--chown="$OWNER_GROUP")
else
  echo "[remote] running without root; skipping --chown"
fi

echo "[remote] staging -> app: $REMOTE_STAGING -> $REMOTE_DIR (owner $OWNER_GROUP)"
echo "[remote] running: rsync ${RSYNC_OPTS[*]} $REMOTE_STAGING/ -> $REMOTE_DIR/"
rsync "${RSYNC_OPTS[@]}" "$REMOTE_STAGING/" "$REMOTE_DIR/"
echo "[remote] rsync promotion done"
REMOTE_SCRIPT

ssh "$REMOTE_HOST" "chmod 750 '$REMOTE_PROMOTE_SCRIPT'"
if ! ssh -tt "$REMOTE_HOST" "sudo -u ${REMOTE_PROMOTE_USER} '$REMOTE_PROMOTE_SCRIPT' '$REMOTE_STAGING' '$REMOTE_DIR' '$OWNER_GROUP' '$RSYNC_DELETE' '$DEBUG'"; then
  PROMOTE_EXIT=$?
  ssh "$REMOTE_HOST" "rm -f '$REMOTE_PROMOTE_SCRIPT'" || true
  exit "$PROMOTE_EXIT"
fi
ssh "$REMOTE_HOST" "rm -f '$REMOTE_PROMOTE_SCRIPT'" || true

if "$SHOULD_REMOVE_REMOTE_VENV"; then
  VENV_REASON=${REMOVE_REMOTE_VENV_REASON:-uv.lock changed}
  echo "→ Removing remote virtualenv at $REMOTE_DIR/.venv ($VENV_REASON)"
  REMOVE_VENV_CMD=$(printf "sudo bash -lc %q" "if [[ -d '$REMOTE_DIR/.venv' ]]; then rm -rf '$REMOTE_DIR/.venv'; fi")
  ssh -tt "$REMOTE_HOST" "$REMOVE_VENV_CMD"
else
  echo "→ uv.lock unchanged; preserving remote virtualenv"
fi

if "$DO_INSTALL"; then
  echo "→ Installing Python deps with uv in remote venv (Python $PY_VER)"
  ENV_SCRIPT="$REMOTE_DIR/scripts/setup_uv_env.sh"
  printf -v REMOTE_CMD 'sudo -u %q -H bash -lc %q' \
    "$SERVICE_USER" \
    "set -euo pipefail; if [[ ! -x \"$ENV_SCRIPT\" ]]; then echo 'Env setup script missing or not executable: $ENV_SCRIPT' >&2; exit 1; fi; \"$ENV_SCRIPT\" --python-version \"$PY_VER\""
  ssh -tt "$REMOTE_HOST" "$REMOTE_CMD"
  ENV_REFRESHED=true
fi

if [[ "$ENV_REFRESHED" != "true" ]]; then
  echo "→ Finalizing remote uv environment via setup script"
  ENV_SCRIPT="$REMOTE_DIR/scripts/setup_uv_env.sh"
  printf -v REMOTE_CMD 'sudo -u %q -H bash -lc %q' \
    "$SERVICE_USER" \
    "set -euo pipefail; if [[ ! -x \"$ENV_SCRIPT\" ]]; then echo 'Env setup script missing or not executable: $ENV_SCRIPT' >&2; exit 1; fi; \"$ENV_SCRIPT\" --python-version \"$PY_VER\""
  ssh -tt "$REMOTE_HOST" "$REMOTE_CMD"
  ENV_REFRESHED=true
fi

PLAYWRIGHT_BIN="$REMOTE_DIR/.venv/bin/playwright"
printf -v REMOTE_PLAYWRIGHT_CMD 'set -euo pipefail; if [[ -x %q ]]; then %q install chromium; else echo "Playwright CLI not found at %s; skipping install" >&2; fi' \
  "$PLAYWRIGHT_BIN" "$PLAYWRIGHT_BIN" "$PLAYWRIGHT_BIN"
ssh -tt "$REMOTE_HOST" "$(printf "sudo -u %q -H bash -lc %q" "$SERVICE_USER" "$REMOTE_PLAYWRIGHT_CMD")"

if "$RESTART_SUP"; then
  echo "→ Reloading Supervisor and restarting programs: ${PROGRAMS[*]}"
  printf -v REMOTE_SUP_CMD 'set -euo pipefail; sudo supervisorctl reread && sudo supervisorctl update'
  for prog in "${PROGRAMS[@]}"; do
    printf -v REMOTE_SUP_CMD '%s && sudo supervisorctl restart %q' "$REMOTE_SUP_CMD" "$prog"
  done
  REMOTE_SUP_CMD+=" && sudo supervisorctl status"
  ssh -tt "$REMOTE_HOST" "$(printf "bash -lc %q" "$REMOTE_SUP_CMD")"
fi

echo "→ Copying .env.racknerd to .env via sudo cp"
CP_ENV_CMD=$(printf "bash -lc %q" "cd '$REMOTE_DIR' && if [[ -f .env.racknerd ]]; then sudo cp .env.racknerd .env && sudo chown '$SERVICE_USER:$SERVICE_GROUP' .env && sudo chmod 600 .env; else echo 'Warning: .env.racknerd missing; skipping copy' >&2; fi")
ssh -tt "$REMOTE_HOST" "$CP_ENV_CMD"

echo "✅ App sync completed to $REMOTE_HOST:$REMOTE_DIR"
