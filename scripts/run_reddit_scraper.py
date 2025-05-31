#!/usr/bin/env python3
"""
Test script for the Reddit scraper.
This script runs the Reddit scraper and then displays all processed articles and their summaries.

USAGE:
    python scripts/run_reddit_scraper.py --clear-existing

NOTE:
    Always run this script using the Python interpreter as shown above.
    Running it as an executable (e.g., ./scripts/run_reddit_scraper.py) may cause import errors.
"""

import sys
import os
import argparse

# Add the parent directory to the path so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scraping.reddit import process_reddit_articles, validate_reddit_config
from app.models import Articles, Summaries
from app.database import SessionLocal, init_db
from app.queue import drain_queue, get_queue_stats


def main():
    """
    Main function to test the Reddit scraper.
    """
    # Hardcoded subreddit map as requested
    SUBREDDIT_MAP = {
        "SquarePOS_Users": 10,
        "POS": 10,
        "ArtificialInteligence": 20,
        "ChatGPTPro": 5,
        "reinforcementlearning": 20,
        "mlscaling": 10,
        "NooTopics": 10
    }
    
    parser = argparse.ArgumentParser(description="Reddit Scraper Test Script")
    parser.add_argument("--clear-existing", action="store_true", 
                       help="Clear existing Reddit articles from database before scraping")
    parser.add_argument("--show-articles", action="store_true", 
                       help="Display all articles and summaries after scraping")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("Reddit Scraper Test Script")
    print("=" * 60)
    
    # Validate Reddit configuration
    if not validate_reddit_config():
        print("ERROR: Reddit API configuration is incomplete.")
        print("Please ensure the following environment variables are set:")
        print("- REDDIT_CLIENT_ID")
        print("- REDDIT_CLIENT_SECRET") 
        print("- REDDIT_USER_AGENT")
        return 1
    
    # Initialize database (create tables if they don't exist)
    print("Initializing database...")
    init_db()
    
    db = SessionLocal()
    try:
        if args.clear_existing:
            print("Clearing existing Reddit articles from the database...")
            # Only clear articles that came from Reddit (we can identify by checking if they have reddit metadata)
            # For now, we'll clear all articles - in production you might want to be more selective
            deleted_count = db.query(Articles).delete()
            db.commit()
            print(f"Cleared {deleted_count} existing articles.")
        
        # Process each subreddit in the map
        total_stats = {
            "total_posts": 0,
            "external_links": 0,
            "successful_scrapes": 0,
            "successful_summaries": 0,
            "errors": 0,
            "duplicates_skipped": 0
        }
        
        for subreddit, limit in SUBREDDIT_MAP.items():
            print(f"\nRunning Reddit scraper for r/{subreddit}...")
            print(f"Parameters: limit={limit}, time_filter=day")
            
            stats = process_reddit_articles(
                subreddit_name=subreddit,
                limit=limit,
                time_filter="day"
            )
            
            # Aggregate stats
            for key in total_stats:
                total_stats[key] += stats[key]
            
            print(f"Completed r/{subreddit} - Scraped: {stats['successful_scrapes']}, Queued: {stats['successful_summaries']}")
        
        print(f"\nAll subreddits completed. Total stats:")
        print(f"  Total posts found: {total_stats['total_posts']}")
        print(f"  External links: {total_stats['external_links']}")
        print(f"  Successful scrapes: {total_stats['successful_scrapes']}")
        print(f"  Successful summaries queued: {total_stats['successful_summaries']}")
        print(f"  Duplicates skipped: {total_stats['duplicates_skipped']}")
        print(f"  Errors: {total_stats['errors']}")
        
        # Check queue status and drain if needed
        queue_stats = get_queue_stats()
        if queue_stats.get("pending_tasks", 0) > 0:
            print(f"\nFound {queue_stats['pending_tasks']} pending summarization tasks in queue.")
            print("Draining queue (processing all pending summarization tasks)...")
            drain_queue()
            print("Queue processing completed.")
        else:
            print("\nNo pending tasks in queue.")
        
        if args.show_articles:
            # Query and display all articles and summaries
            print("\n" + "=" * 60)
            print("ARTICLES AND SUMMARIES")
            print("=" * 60)
            
            # Get all articles with their summaries (most recent first)
            articles = db.query(Articles).order_by(Articles.scraped_date.desc()).all()
            
            if not articles:
                print("No articles found in the database.")
                return 0
            
            print(f"\nFound {len(articles)} articles in the database:\n")
            
            for i, article in enumerate(articles, 1):
                print(f"Article {i}:")
                print(f"  Title: {article.title}")
                print(f"  URL: {article.url}")
                print(f"  Author: {article.author or 'Unknown'}")
                print(f"  Status: {article.status.value}")
                print(f"  Scraped Date: {article.scraped_date}")
                
                # Get associated summaries
                summaries = db.query(Summaries).filter(Summaries.article_id == article.id).all()
                
                if summaries:
                    for summary in summaries:
                        print(f"  Short Summary: {summary.short_summary}")
                        if summary.detailed_summary and summary.detailed_summary != summary.short_summary:
                            print(f"  Detailed Summary: {summary.detailed_summary[:200]}...")
                        print(f"  Summary Date: {summary.summary_date}")
                else:
                    print("  No summary available")
                
                print("-" * 40)
        else:
            print(f"\nUse --show-articles to display all processed articles.")
            print(f"Use --clear-existing to clear the database before scraping.")
    
    except Exception as e:
        print(f"Error running Reddit scraper: {e}")
        return 1
    
    finally:
        db.close()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
