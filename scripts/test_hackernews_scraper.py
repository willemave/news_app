#!/usr/bin/env python3
"""
Test script for the HackerNews scraper.
This script runs the HackerNews scraper and then displays all processed articles and their summaries.
"""

import sys
import os

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scraping.hackernews_scraper import process_hackernews_articles
from app.models import Articles, Summaries
from app.database import SessionLocal, init_db
from app.queue import drain_queue, get_queue_stats

def main():
    """
    Main function to test the HackerNews scraper.
    """
    print("=" * 60)
    print("HackerNews Scraper Test Script")
    print("=" * 60)
    
    # Initialize database (create tables if they don't exist)
    print("Initializing database...")
    init_db()
    
    db = SessionLocal()
    try:
        print("Clearing existing articles from the database...")
        db.query(Articles).delete()
        db.commit()
        print("Existing articles cleared.")
        
        # Run the HackerNews scraper
        print("\nRunning HackerNews scraper...")
        stats = process_hackernews_articles()
        
        print(f"\nScraping completed with stats:")
        print(f"  Total links found: {stats['total_links']}")
        print(f"  Successful scrapes: {stats['successful_scrapes']}")
        print(f"  Successful summaries queued: {stats['successful_summaries']}")
        print(f"  Errors: {stats['errors']}")
        
        # Check queue status and drain if needed
        queue_stats = get_queue_stats()
        if queue_stats.get("pending_tasks", 0) > 0:
            print(f"\nFound {queue_stats['pending_tasks']} pending summarization tasks in queue.")
            print("Draining queue (processing all pending summarization tasks)...")
            drain_queue()
            print("Queue processing completed.")
        else:
            print("\nNo pending tasks in queue.")
        
        # Query and display all articles and summaries
        print("\n" + "=" * 60)
        print("ARTICLES AND SUMMARIES")
        print("=" * 60)
        
        # Get all articles with their summaries
        articles = db.query(Articles).all()
        
        if not articles:
            print("No articles found in the database.")
            return
        
        print(f"\nFound {len(articles)} articles in the database:\n")
        
        for i, article in enumerate(articles, 1):
            print(f"Article {i}:")
            print(f"  Title: {article.title}")
            print(f"  URL: {article.url}")
            print(f"  Status: {article.status.value}")
            print(f"  Scraped Date: {article.scraped_date}")
            
            # Get associated summaries
            summaries = db.query(Summaries).filter(Summaries.article_id == article.id).all()
            
            if summaries:
                for summary in summaries:
                    print(f"  Summary: {summary.short_summary}")
                    if summary.detailed_summary and summary.detailed_summary != summary.short_summary:
                        print(f"  Detailed Summary: {summary.detailed_summary}")
                    print(f"  Summary Date: {summary.summary_date}")
            else:
                print("  No summary available")
            
            print("-" * 40)
    
    except Exception as e:
        print(f"Error querying database: {e}")
    
    finally:
        db.close()

if __name__ == "__main__":
    main()
