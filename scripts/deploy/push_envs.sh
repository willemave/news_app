#!/usr/bin/env bash
set -euo pipefail

# Lightweight helper to force `.env` to mirror `.env.racknerd` on the remote host.
# Defaults mirror push_app.sh, but we avoid any rsync logic.

REMOTE_HOST="willem@192.3.250.10"
REMOTE_DIR="/opt/news_app"
OWNER_GROUP="newsapp:newsapp"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--host)
      REMOTE_HOST="$2"
      shift 2
      ;;
    -d|--dir)
      REMOTE_DIR="$2"
      shift 2
      ;;
    -o|--owner)
      OWNER_GROUP="$2"
      shift 2
      ;;
    --help|-\?)
      cat <<'USAGE'
Usage: scripts/deploy/push_envs.sh [--host user@host] [--dir /remote/path] [--owner user:group]

Copies .env.racknerd to .env on the remote using sudo cp. No rsync involved.
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

echo "→ Copying .env.racknerd to .env on $REMOTE_HOST:$REMOTE_DIR"
CP_ENV_CMD=$(printf "bash -lc %q" "cd '$REMOTE_DIR' && if [[ -f .env.racknerd ]]; then sudo cp .env.racknerd .env && sudo chown '$SERVICE_USER:$SERVICE_GROUP' .env && sudo chmod 600 .env; else echo 'Warning: .env.racknerd missing; skipping copy' >&2; fi")
ssh -tt "$REMOTE_HOST" "$CP_ENV_CMD"

echo "✅ Remote .env updated"
