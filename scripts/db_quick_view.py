#!/usr/bin/env python3
"""
Quick database viewer - simplified version for fast viewing
"""

import sqlite3

def quick_view():
    """Quick view of database contents with basic formatting."""
    try:
        conn = sqlite3.connect("news_app.db")
        cursor = conn.cursor()
        
        # Quick stats
        cursor.execute("SELECT COUNT(*) FROM links")
        links_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM articles")
        articles_count = cursor.fetchone()[0]
        
        print(f"📊 Database Stats: {links_count} links, {articles_count} articles")
        print("-" * 50)
        
        # Recent links - ALL COLUMNS
        print("\n🔗 Recent Links (last 10) - ALL COLUMNS:")
        cursor.execute("""
            SELECT id, url, source, status, created_date, processed_date, error_message 
            FROM links 
            ORDER BY id DESC 
            LIMIT 10
        """)
        
        for row in cursor.fetchall():
            url = row[1][:40] + "..." if len(row[1]) > 40 else row[1]
            error = row[6][:30] + "..." if row[6] and len(row[6]) > 30 else (row[6] or "None")
            print(f"  ID: {row[0]}")
            print(f"    URL: {url}")
            print(f"    Source: {row[2]}")
            print(f"    Status: {row[3]}")
            print(f"    Created: {row[4]}")
            print(f"    Processed: {row[5] or 'None'}")
            print(f"    Error: {error}")
            print()
        
        # Recent articles if any - ALL COLUMNS
        if articles_count > 0:
            print("\n📰 Recent Articles (last 5) - ALL COLUMNS:")
            cursor.execute("""
                SELECT id, title, url, author, publication_date, scraped_date, 
                       short_summary, detailed_summary, summary_date, link_id 
                FROM articles 
                ORDER BY id DESC 
                LIMIT 5
            """)
            
            for row in cursor.fetchall():
                title = row[1][:40] + "..." if row[1] and len(row[1]) > 40 else (row[1] or "No title")
                url = row[2][:40] + "..." if len(row[2]) > 40 else row[2]
                short_summary = row[6][:50] + "..." if row[6] and len(row[6]) > 50 else (row[6] or "None")
                detailed_summary = row[7][:50] + "..." if row[7] and len(row[7]) > 50 else (row[7] or "None")
                print(f"  ID: {row[0]}")
                print(f"    Title: {title}")
                print(f"    URL: {url}")
                print(f"    Author: {row[3] or 'None'}")
                print(f"    Publication Date: {row[4] or 'None'}")
                print(f"    Scraped Date: {row[5]}")
                print(f"    Short Summary: {short_summary}")
                print(f"    Detailed Summary: {detailed_summary}")
                print(f"    Summary Date: {row[8] or 'None'}")
                print(f"    Link ID: {row[9] or 'None'}")
                print()
        
        conn.close()
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    quick_view()
