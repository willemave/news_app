#!/usr/bin/env python3
"""
Migration script to add 'skipped' status to LinkStatus enum in SQLite database.
Run with: python scripts/migrations/add_skipped_status.py
"""

import sqlite3
import os

def get_db_path():
    """Get the database path from environment or use default."""
    return os.getenv('DATABASE_URL', './news_app.db').replace('sqlite:///', '')

def migrate_link_status():
    """Add 'skipped' status to the links table if not already present."""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if 'skipped' status already exists
        cursor.execute("SELECT DISTINCT status FROM links WHERE status = 'skipped'")
        if cursor.fetchone():
            print("'skipped' status already exists in database")
            return True
        
        # SQLite doesn't support ALTER TYPE for enums, but since we're using string values,
        # we just need to ensure the application can handle the new value
        print("Migration complete - SQLite will accept 'skipped' status values")
        print("The enum change in models.py is sufficient for SQLite")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False

if __name__ == "__main__":
    print("Running migration to add 'skipped' status to LinkStatus enum...")
    success = migrate_link_status()
    if success:
        print("Migration completed successfully!")
    else:
        print("Migration failed!")