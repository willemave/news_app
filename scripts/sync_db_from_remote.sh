#!/bin/bash

# Script to safely copy remote SQLite database to local machine
# Uses sqlite3 .backup command to ensure consistent copy even if DB is in use
# Usage: ./scripts/sync_db_from_remote.sh [destination_path]

set -e

REMOTE_HOST="willem@192.3.250.10"
REMOTE_DB_PATH="/data/news_app.db"
REMOTE_BACKUP_PATH="/tmp/news_app_backup.db"
DEFAULT_LOCAL_PATH="./news_app.db"

# Use provided destination or default
LOCAL_PATH="${1:-$DEFAULT_LOCAL_PATH}"

echo "📦 Syncing database from remote (safe backup mode)..."
echo "   Remote: ${REMOTE_HOST}:${REMOTE_DB_PATH}"
echo "   Local:  ${LOCAL_PATH}"
echo ""

# Create local directory if it doesn't exist
mkdir -p "$(dirname "$LOCAL_PATH")"

# Create a safe backup on the remote server using sqlite3 .backup
echo "🔒 Creating safe backup on remote server..."
ssh "${REMOTE_HOST}" "sqlite3 '${REMOTE_DB_PATH}' '.backup ${REMOTE_BACKUP_PATH}'"

# Copy the backup file to local
echo "📥 Downloading backup..."
scp "${REMOTE_HOST}:${REMOTE_BACKUP_PATH}" "${LOCAL_PATH}"

# Clean up the temporary backup on remote
echo "🧹 Cleaning up remote backup..."
ssh "${REMOTE_HOST}" "rm -f '${REMOTE_BACKUP_PATH}'"

echo ""
echo "✅ Database copied successfully to ${LOCAL_PATH}"
