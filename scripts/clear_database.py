#!/usr/bin/env python3
"""
Simple script to clear all database tables.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.append(str(Path(__file__).parent.parent))

from app.core.db import get_db
from app.models.schema import Content, ProcessingTask


def clear_all_tables():
    """Clear all data from database tables."""
    with get_db() as db:
        # Delete processing tasks first (no foreign key constraints)
        tasks_deleted = db.query(ProcessingTask).delete()
        print(f"Deleted {tasks_deleted} processing tasks")
        
        # Delete content (unified articles and podcasts)
        content_deleted = db.query(Content).delete()
        print(f"Deleted {content_deleted} content items")
        
        print("\nAll tables cleared successfully!")


def confirm_action():
    """Ask user to confirm the destructive action."""
    response = input("This will delete ALL data from the database. Are you sure? (yes/no): ")
    return response.lower() in ['yes', 'y']


if __name__ == "__main__":
    print("Database Table Cleaner")
    print("=" * 30)
    
    if not confirm_action():
        print("Operation cancelled.")
        sys.exit(0)
    
    try:
        clear_all_tables()
    except Exception as e:
        print(f"Failed to clear database: {e}")
        sys.exit(1)