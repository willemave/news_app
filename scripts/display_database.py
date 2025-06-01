#!/usr/bin/env python3
"""
Script to display the contents of the SQLite database tables in a formatted table.
Shows both the links and articles tables.
"""

import sqlite3
from datetime import datetime
from typing import List, Tuple, Any

def format_table(headers: List[str], rows: List[Tuple], title: str) -> str:
    """Format data as a table with proper alignment."""
    if not rows:
        return f"\n{title}\n{'=' * len(title)}\nNo data found.\n"
    
    # Calculate column widths
    col_widths = [len(header) for header in headers]
    for row in rows:
        for i, cell in enumerate(row):
            cell_str = str(cell) if cell is not None else "NULL"
            col_widths[i] = max(col_widths[i], len(cell_str))
    
    # Create format string
    format_str = " | ".join(f"{{:<{width}}}" for width in col_widths)
    
    # Build table
    result = f"\n{title}\n{'=' * len(title)}\n"
    
    # Header
    result += format_str.format(*headers) + "\n"
    result += "-" * (sum(col_widths) + 3 * (len(headers) - 1)) + "\n"
    
    # Rows
    for row in rows:
        formatted_row = []
        for cell in row:
            if cell is None:
                formatted_row.append("NULL")
            elif isinstance(cell, datetime):
                formatted_row.append(cell.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                formatted_row.append(str(cell))
        result += format_str.format(*formatted_row) + "\n"
    
    result += f"\nTotal rows: {len(rows)}\n"
    return result

def display_links_table(cursor: sqlite3.Cursor) -> str:
    """Display the links table."""
    cursor.execute("""
        SELECT id, url, source, status, created_date, processed_date, error_message
        FROM links
        ORDER BY id
    """)
    
    headers = ["ID", "URL", "Source", "Status", "Created Date", "Processed Date", "Error Message"]
    rows = cursor.fetchall()
    
    return format_table(headers, rows, "LINKS TABLE")

def display_articles_table(cursor: sqlite3.Cursor) -> str:
    """Display the articles table."""
    cursor.execute("""
        SELECT id, title, url, author, publication_date, scraped_date, 
               short_summary, detailed_summary, summary_date, link_id
        FROM articles
        ORDER BY id
    """)
    
    headers = ["ID", "Title", "URL", "Author", "Pub Date", "Scraped Date", 
               "Short Summary", "Detailed Summary", "Summary Date", "Link ID"]
    rows = cursor.fetchall()
    
    # Truncate long text fields for display
    truncated_rows = []
    for row in rows:
        truncated_row = list(row)
        # Truncate title, short_summary, detailed_summary if they're too long
        if truncated_row[1] and len(str(truncated_row[1])) > 50:
            truncated_row[1] = str(truncated_row[1])[:47] + "..."
        if truncated_row[6] and len(str(truncated_row[6])) > 50:
            truncated_row[6] = str(truncated_row[6])[:47] + "..."
        if truncated_row[7] and len(str(truncated_row[7])) > 50:
            truncated_row[7] = str(truncated_row[7])[:47] + "..."
        truncated_rows.append(tuple(truncated_row))
    
    return format_table(headers, truncated_rows, "ARTICLES TABLE")

def display_database_stats(cursor: sqlite3.Cursor) -> str:
    """Display database statistics."""
    stats = []
    
    # Links stats
    cursor.execute("SELECT COUNT(*) FROM links")
    total_links = cursor.fetchone()[0]
    
    cursor.execute("SELECT status, COUNT(*) FROM links GROUP BY status")
    link_status_counts = cursor.fetchall()
    
    # Articles stats
    cursor.execute("SELECT COUNT(*) FROM articles")
    total_articles = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM articles WHERE short_summary IS NOT NULL")
    articles_with_summary = cursor.fetchone()[0]
    
    result = "\nDATABASE STATISTICS\n"
    result += "=" * 19 + "\n"
    result += f"Total Links: {total_links}\n"
    
    if link_status_counts:
        result += "Link Status Breakdown:\n"
        for status, count in link_status_counts:
            result += f"  {status}: {count}\n"
    
    result += f"\nTotal Articles: {total_articles}\n"
    result += f"Articles with Summary: {articles_with_summary}\n"
    
    return result

def main():
    """Main function to display database contents."""
    db_path = "news_app.db"
    
    try:
        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("NEWS APP DATABASE CONTENTS")
        print("=" * 30)
        
        # Display statistics
        print(display_database_stats(cursor))
        
        # Display links table
        print(display_links_table(cursor))
        
        # Display articles table
        print(display_articles_table(cursor))
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    except FileNotFoundError:
        print(f"Database file '{db_path}' not found.")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
