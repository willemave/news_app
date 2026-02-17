#!/usr/bin/env bash
set -euo pipefail

# Lightweight helper to push local `.env.racknerd` to remote, then mirror to `.env`.
# Defaults mirror push_app.sh.

REMOTE_HOST="willem@192.3.250.10"
REMOTE_DIR="/opt/news_app"
OWNER_GROUP="newsapp:newsapp"
SOURCE_ENV_FILE=".env.racknerd"
REMOTE_STAGING_DIR="/tmp/news_app_env_sync"
REMOTE_PORT="22"

require_option_value() {
  local option_name="$1"
  local option_value="${2:-}"
  if [[ -z "$option_value" || "$option_value" == -* ]]; then
    echo "Option $option_name requires a value" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--host)
      require_option_value "$1" "${2:-}"
      REMOTE_HOST="$2"
      shift 2
      ;;
    -d|--dir)
      require_option_value "$1" "${2:-}"
      REMOTE_DIR="$2"
      shift 2
      ;;
    -o|--owner)
      require_option_value "$1" "${2:-}"
      OWNER_GROUP="$2"
      shift 2
      ;;
    -p|--port)
      require_option_value "$1" "${2:-}"
      REMOTE_PORT="$2"
      shift 2
      ;;
    -s|--source)
      require_option_value "$1" "${2:-}"
      SOURCE_ENV_FILE="$2"
      shift 2
      ;;
    --staging)
      require_option_value "$1" "${2:-}"
      REMOTE_STAGING_DIR="$2"
      shift 2
      ;;
    --help|-\?)
      cat <<'USAGE'
Usage: scripts/deploy/push_envs.sh [--host user@host] [--port 22] [--dir /remote/path] [--owner user:group] [--source .env.racknerd]

Pushes local .env.racknerd to remote and mirrors it to .env using sudo cp.
USAGE
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

if [[ "$OWNER_GROUP" == *:* ]]; then
  SERVICE_USER="${OWNER_GROUP%%:*}"
  SERVICE_GROUP="${OWNER_GROUP##*:}"
else
  SERVICE_USER="$OWNER_GROUP"
  SERVICE_GROUP="$OWNER_GROUP"
fi

if [[ ! -f "$SOURCE_ENV_FILE" ]]; then
  echo "Local source env file not found: $SOURCE_ENV_FILE" >&2
  exit 1
fi

SSH_OPTS=(-p "$REMOTE_PORT" -o BatchMode=yes -o StrictHostKeyChecking=accept-new)

echo "→ Preparing remote staging dir on $REMOTE_HOST:$REMOTE_STAGING_DIR"
ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" "mkdir -p '$REMOTE_STAGING_DIR' && chmod 700 '$REMOTE_STAGING_DIR'"

echo "→ Uploading $SOURCE_ENV_FILE to $REMOTE_HOST:$REMOTE_STAGING_DIR/.env.racknerd"
rsync -az --progress -e "ssh -p $REMOTE_PORT -o BatchMode=yes -o StrictHostKeyChecking=accept-new" \
  "$SOURCE_ENV_FILE" "$REMOTE_HOST:$REMOTE_STAGING_DIR/.env.racknerd"

echo "→ Promoting remote env files in $REMOTE_DIR"
PROMOTE_ENV_CMD=$(printf "bash -lc %q" "sudo mkdir -p '$REMOTE_DIR' && sudo cp '$REMOTE_STAGING_DIR/.env.racknerd' '$REMOTE_DIR/.env.racknerd' && sudo cp '$REMOTE_DIR/.env.racknerd' '$REMOTE_DIR/.env' && sudo chown '$SERVICE_USER:$SERVICE_GROUP' '$REMOTE_DIR/.env.racknerd' '$REMOTE_DIR/.env' && sudo chmod 600 '$REMOTE_DIR/.env.racknerd' '$REMOTE_DIR/.env'")
ssh "${SSH_OPTS[@]}" "$REMOTE_HOST" "$PROMOTE_ENV_CMD"

echo "✅ Remote .env.racknerd and .env updated"
