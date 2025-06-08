#!/usr/bin/env python3
"""
Migration script to add 'status' column to the 'articles' table in SQLite.
Run with: python scripts/migrations/add_status_to_articles.py
"""

import sqlite3
import os
import sys

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.config import settings

def get_db_path():
    """Get the database path from settings."""
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./news_app.db')
    return db_url.replace('sqlite:///', '')

def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def migrate_add_status_to_articles():
    """Add 'status' column to the articles table if it doesn't exist."""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        table_name = "articles"
        column_name = "status"
        
        if column_exists(cursor, table_name, column_name):
            print(f"Column '{column_name}' already exists in table '{table_name}'.")
            return True
            
        print(f"Adding column '{column_name}' to table '{table_name}'...")
        # Default to 'new' for existing rows
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} VARCHAR DEFAULT 'new'")
        conn.commit()
        print("Migration successful: Column added.")
        
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    print("Running migration to add 'status' to 'articles' table...")
    success = migrate_add_status_to_articles()
    if success:
        print("Migration script finished.")
    else:
        print("Migration script failed.")