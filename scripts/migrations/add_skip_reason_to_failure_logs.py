#!/usr/bin/env python3
"""
Migration script to add skip_reason column to failure_logs table.
"""
import sqlite3
import sys
from pathlib import Path

# Add the app directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.config import settings

def add_skip_reason_column():
    """Add skip_reason column to failure_logs table."""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(failure_logs)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'skip_reason' not in columns:
            print("Adding skip_reason column to failure_logs table...")
            cursor.execute("ALTER TABLE failure_logs ADD COLUMN skip_reason TEXT")
            conn.commit()
            print("Successfully added skip_reason column.")
        else:
            print("skip_reason column already exists in failure_logs table.")
        
        conn.close()
        
    except Exception as e:
        print(f"Error adding skip_reason column: {e}")
        sys.exit(1)

if __name__ == "__main__":
    add_skip_reason_column()