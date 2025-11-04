#!/bin/bash
# Database backup script for news_app
# Usage: ./backup_database.sh
# Cron: 0 2 * * * /path/to/backup_database.sh >> /var/log/newsly/backup.log 2>&1

set -euo pipefail

# Configuration
SOURCE_DB="/data/news_app.db"
BACKUP_DIR="/data/backups"
RETENTION_DAYS=30  # Keep backups for 30 days
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/news_app_${TIMESTAMP}.db"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

# Create backup directory if it doesn't exist
if [ ! -d "$BACKUP_DIR" ]; then
    log "Creating backup directory: $BACKUP_DIR"
    mkdir -p "$BACKUP_DIR"
fi

# Check if source database exists
if [ ! -f "$SOURCE_DB" ]; then
    log "ERROR: Source database not found: $SOURCE_DB"
    exit 1
fi

# Perform backup using SQLite's .backup command (safer than cp for active DB)
log "Starting backup: $SOURCE_DB -> $BACKUP_FILE"

if command -v sqlite3 &> /dev/null; then
    # Use SQLite backup command (proper online backup)
    sqlite3 "$SOURCE_DB" ".backup '$BACKUP_FILE'"
    BACKUP_METHOD="sqlite3 .backup"
else
    # Fallback to cp (less safe for active DB)
    log "WARNING: sqlite3 not found, using cp (less safe for active database)"
    cp "$SOURCE_DB" "$BACKUP_FILE"
    BACKUP_METHOD="cp"
fi

# Verify backup was created
if [ ! -f "$BACKUP_FILE" ]; then
    log "ERROR: Backup file was not created: $BACKUP_FILE"
    exit 1
fi

# Get file sizes
SOURCE_SIZE=$(stat -f%z "$SOURCE_DB" 2>/dev/null || stat -c%s "$SOURCE_DB" 2>/dev/null)
BACKUP_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE" 2>/dev/null)

log "Backup completed successfully using $BACKUP_METHOD"
log "Source size: $(numfmt --to=iec-i --suffix=B $SOURCE_SIZE 2>/dev/null || echo ${SOURCE_SIZE} bytes)"
log "Backup size: $(numfmt --to=iec-i --suffix=B $BACKUP_SIZE 2>/dev/null || echo ${BACKUP_SIZE} bytes)"

# Rotate old backups (delete backups older than RETENTION_DAYS)
log "Cleaning up backups older than $RETENTION_DAYS days..."
DELETED_COUNT=0

find "$BACKUP_DIR" -name "news_app_*.db" -type f -mtime +$RETENTION_DAYS -print0 | while IFS= read -r -d '' old_backup; do
    log "Deleting old backup: $(basename "$old_backup")"
    rm -f "$old_backup"
    ((DELETED_COUNT++))
done

if [ $DELETED_COUNT -gt 0 ]; then
    log "Deleted $DELETED_COUNT old backup(s)"
else
    log "No old backups to delete"
fi

# Summary
BACKUP_COUNT=$(find "$BACKUP_DIR" -name "news_app_*.db" -type f | wc -l)
log "Backup complete. Total backups in directory: $BACKUP_COUNT"

exit 0
