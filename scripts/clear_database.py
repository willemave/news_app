#!/usr/bin/env python3
"""
Simple script to clear all database tables.
"""

import sys
from pathlib import Path

# Add the parent directory to the path so we can import from app
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Links, Articles, FailureLogs, CronLogs


def clear_all_tables():
    """Clear all data from database tables."""
    db = SessionLocal()
    try:
        # Delete in order to respect foreign key constraints
        # Articles reference Links, so delete Articles first
        articles_deleted = db.query(Articles).delete()
        print(f"Deleted {articles_deleted} articles")
        
        # Delete failure logs (they reference links)
        failure_logs_deleted = db.query(FailureLogs).delete()
        print(f"Deleted {failure_logs_deleted} failure logs")
        
        # Delete links
        links_deleted = db.query(Links).delete()
        print(f"Deleted {links_deleted} links")
        
        # Delete cron logs (no foreign key dependencies)
        cron_logs_deleted = db.query(CronLogs).delete()
        print(f"Deleted {cron_logs_deleted} cron logs")
        
        # Commit the transaction
        db.commit()
        print("\nAll tables cleared successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"Error clearing tables: {e}")
        raise
    finally:
        db.close()


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