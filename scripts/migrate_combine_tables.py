#!/usr/bin/env python3
"""
Migration script to combine Articles and Summaries tables.

This script:
1. Adds new columns to Articles table (short_summary, detailed_summary, summary_date, source)
2. Migrates data from Summaries table to Articles table
3. Drops the Summaries table
4. Updates existing articles with source information based on URL patterns
"""

import sqlite3
import sys
from datetime import datetime
from urllib.parse import urlparse

def migrate_database(db_path: str = "news_app.db"):
    """
    Perform the database migration.
    
    Args:
        db_path: Path to the SQLite database file
    """
    print(f"Starting migration of database: {db_path}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if migration is needed
        cursor.execute("PRAGMA table_info(articles)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'source' in columns:
            print("Migration already completed - 'source' column exists in articles table")
            return
        
        print("Step 1: Adding new columns to articles table...")
        
        # Add new columns to articles table
        cursor.execute("ALTER TABLE articles ADD COLUMN short_summary TEXT")
        cursor.execute("ALTER TABLE articles ADD COLUMN detailed_summary TEXT")
        cursor.execute("ALTER TABLE articles ADD COLUMN summary_date DATETIME")
        cursor.execute("ALTER TABLE articles ADD COLUMN source VARCHAR DEFAULT 'unknown'")
        
        print("Step 2: Migrating data from summaries table to articles table...")
        
        # Check if summaries table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='summaries'")
        if cursor.fetchone():
            # Migrate data from summaries to articles
            cursor.execute("""
                UPDATE articles 
                SET 
                    short_summary = (
                        SELECT short_summary 
                        FROM summaries 
                        WHERE summaries.article_id = articles.id 
                        LIMIT 1
                    ),
                    detailed_summary = (
                        SELECT detailed_summary 
                        FROM summaries 
                        WHERE summaries.article_id = articles.id 
                        LIMIT 1
                    ),
                    summary_date = (
                        SELECT summary_date 
                        FROM summaries 
                        WHERE summaries.article_id = articles.id 
                        LIMIT 1
                    )
                WHERE EXISTS (
                    SELECT 1 FROM summaries WHERE summaries.article_id = articles.id
                )
            """)
            
            migrated_count = cursor.rowcount
            print(f"Migrated summaries for {migrated_count} articles")
            
            # Drop the summaries table
            print("Step 3: Dropping summaries table...")
            cursor.execute("DROP TABLE summaries")
        else:
            print("Summaries table not found - skipping data migration")
        
        print("Step 4: Updating source information for existing articles...")
        
        # Update source based on URL patterns or other heuristics
        # For now, we'll set all existing articles to 'unknown' and let future scraping populate correctly
        cursor.execute("UPDATE articles SET source = 'unknown' WHERE source IS NULL OR source = ''")
        
        # Try to infer source from URL patterns for some common cases
        cursor.execute("""
            UPDATE articles 
            SET source = 'hackernews' 
            WHERE url LIKE '%news.ycombinator.com%' OR url LIKE '%ycombinator.com%'
        """)
        
        cursor.execute("""
            UPDATE articles 
            SET source = 'reddit' 
            WHERE url LIKE '%reddit.com%' OR url LIKE '%redd.it%'
        """)
        
        # Create index on source column for better performance
        print("Step 5: Creating index on source column...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source)")
        
        # Commit all changes
        conn.commit()
        
        print("Migration completed successfully!")
        
        # Print summary statistics
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]
        
        cursor.execute("SELECT source, COUNT(*) FROM articles GROUP BY source")
        source_counts = cursor.fetchall()
        
        print(f"\nMigration Summary:")
        print(f"Total articles: {total_articles}")
        print("Articles by source:")
        for source, count in source_counts:
            print(f"  {source}: {count}")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        raise
    
    finally:
        conn.close()


def verify_migration(db_path: str = "news_app.db"):
    """
    Verify that the migration was successful.
    
    Args:
        db_path: Path to the SQLite database file
    """
    print(f"\nVerifying migration for database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check table structure
        cursor.execute("PRAGMA table_info(articles)")
        columns = cursor.fetchall()
        
        expected_columns = [
            'id', 'title', 'url', 'author', 'publication_date', 
            'scraped_date', 'status', 'short_summary', 'detailed_summary', 
            'summary_date', 'source'
        ]
        
        actual_columns = [column[1] for column in columns]
        
        print("Articles table columns:")
        for column in columns:
            print(f"  {column[1]} ({column[2]})")
        
        missing_columns = set(expected_columns) - set(actual_columns)
        if missing_columns:
            print(f"ERROR: Missing columns: {missing_columns}")
            return False
        
        # Check that summaries table is gone
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='summaries'")
        if cursor.fetchone():
            print("ERROR: Summaries table still exists")
            return False
        
        # Check data integrity
        cursor.execute("SELECT COUNT(*) FROM articles WHERE source IS NOT NULL")
        articles_with_source = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM articles")
        total_articles = cursor.fetchone()[0]
        
        if articles_with_source != total_articles:
            print(f"WARNING: {total_articles - articles_with_source} articles have NULL source")
        
        print("Migration verification completed successfully!")
        return True
        
    except Exception as e:
        print(f"Error during verification: {e}")
        return False
    
    finally:
        conn.close()


if __name__ == "__main__":
    db_path = sys.argv[1] if len(sys.argv) > 1 else "news_app.db"
    
    print("=== Database Migration: Combining Articles and Summaries Tables ===")
    print(f"Database: {db_path}")
    print(f"Timestamp: {datetime.now()}")
    print()
    
    try:
        migrate_database(db_path)
        verify_migration(db_path)
        print("\n=== Migration completed successfully! ===")
    except Exception as e:
        print(f"\n=== Migration failed: {e} ===")
        sys.exit(1)
