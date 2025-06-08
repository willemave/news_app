#!/usr/bin/env python3
"""
Migration script to add 'podcasts' table to the SQLite database.
Run with: python scripts/migrations/add_podcasts_table.py
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

def table_exists(cursor, table_name):
    """Check if a table exists in the database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def migrate_add_podcasts_table():
    """Add 'podcasts' table to the database if it doesn't exist."""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        table_name = "podcasts"
        
        if table_exists(cursor, table_name):
            print(f"Table '{table_name}' already exists.")
            return True
            
        print(f"Creating table '{table_name}'...")
        
        # Create podcasts table
        create_table_sql = """
        CREATE TABLE podcasts (
            id INTEGER PRIMARY KEY,
            title VARCHAR NOT NULL,
            url VARCHAR NOT NULL UNIQUE,
            enclosure_url VARCHAR NOT NULL,
            file_path VARCHAR,
            transcribed_text_path VARCHAR,
            short_summary TEXT,
            detailed_summary TEXT,
            publication_date DATETIME,
            download_date DATETIME,
            podcast_feed_name VARCHAR NOT NULL,
            status VARCHAR DEFAULT 'new',
            created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            error_message TEXT
        )
        """
        
        cursor.execute(create_table_sql)
        
        # Create indexes
        cursor.execute("CREATE INDEX ix_podcasts_url ON podcasts (url)")
        cursor.execute("CREATE INDEX ix_podcasts_status ON podcasts (status)")
        cursor.execute("CREATE INDEX ix_podcasts_podcast_feed_name ON podcasts (podcast_feed_name)")
        
        conn.commit()
        print("Migration successful: Podcasts table created with indexes.")
        
        return True
        
    except Exception as e:
        print(f"Error during migration: {e}")
        return False
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    print("Running migration to add 'podcasts' table...")
    success = migrate_add_podcasts_table()
    if success:
        print("Migration script finished.")
    else:
        print("Migration script failed.")