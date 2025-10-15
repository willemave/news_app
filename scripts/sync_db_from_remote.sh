#!/bin/bash

# Script to copy remote database to local machine
# Usage: ./scripts/sync_db_from_remote.sh [destination_path]

set -e

REMOTE_HOST="willem@192.3.250.10"
REMOTE_DB_PATH="/data/news_app.db"
DEFAULT_LOCAL_PATH="./news_app.db"

# Use provided destination or default
LOCAL_PATH="${1:-$DEFAULT_LOCAL_PATH}"

echo "📦 Copying database from remote..."
echo "   Remote: ${REMOTE_HOST}:${REMOTE_DB_PATH}"
echo "   Local:  ${LOCAL_PATH}"
echo ""

# Create local directory if it doesn't exist
mkdir -p "$(dirname "$LOCAL_PATH")"

# Copy the database file
scp "${REMOTE_HOST}:${REMOTE_DB_PATH}" "${LOCAL_PATH}"

echo ""
echo "✅ Database copied successfully to ${LOCAL_PATH}"
