#!/usr/bin/env python3
"""
Unified test script for HackerNews and Reddit scrapers.
Always runs both scrapers. Supports Reddit flags for clearing existing data and showing results.
"""

import sys
import os
import argparse

# Add parent directory so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scraping.hackernews_scraper import process_hackernews_articles
from app.scraping.reddit import process_reddit_articles, validate_reddit_config
from app.models import Articles
from app.database import SessionLocal, init_db
from app.queue import drain_queue, get_queue_stats

# Hardcoded subreddit map as before
SUBREDDIT_MAP = {
    "SquarePOS_Users": 10,
    "POS": 10,
    "ArtificialInteligence": 20,
    "ChatGPTPro": 5,
    "reinforcementlearning": 20,
    "mlscaling": 10,
    "NooTopics": 10
}


def main():
    parser = argparse.ArgumentParser(description="Unified Scrapers Test Script")
    parser.add_argument(
        "--clear-existing",
        action="store_true",
        help="Clear existing articles before Reddit scraper"
    )
    parser.add_argument(
        "--show-articles",
        action="store_true",
        help="Display all articles and summaries after both scrapers"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Unified Scrapers Test Script")
    print("=" * 60)

    print("Initializing database...")
    init_db()
    db = SessionLocal()

    try:
        if args.clear_existing:
            print("Clearing ALL existing articles from the database (due to --clear-existing)...")
            db.query(Articles).delete()
            db.commit()
            print("All existing articles cleared.")

        # HackerNews scraper
        print("\n" + "=" * 60)
        print("HackerNews Scraper")
        print("=" * 60)
        # Clearing is now handled globally by --clear-existing flag at the start

        print("\nRunning HackerNews scraper...")
        hn_stats = process_hackernews_articles()
        print("\nHackerNews stats:")
        print(f"  Total links found: {hn_stats['total_links']}")
        print(f"  Queued links: {hn_stats['queued_links']}")
        print(f"  Errors: {hn_stats['errors']}")

        queue_stats = get_queue_stats()
        if queue_stats.get("pending_tasks", 0) > 0:
            print(f"\nFound {queue_stats['pending_tasks']} pending summarization tasks.")
            print("Draining queue...")
            drain_queue()
            print("Queue processing completed.")
        else:
            print("\nNo pending tasks in queue.")

        # Reddit scraper
        print("\n" + "=" * 60)
        print("Reddit Scraper")
        print("=" * 60)

        if not validate_reddit_config():
            print("ERROR: Reddit API configuration is incomplete.")
            print("Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT.")
            return 1
        # Clearing is now handled globally by --clear-existing flag at the start

        total_stats = {
            "total_posts": 0,
            "external_links": 0,
            "queued_links": 0,
            "errors": 0
        }

        for subreddit, limit in SUBREDDIT_MAP.items():
            print(f"\nRunning Reddit scraper for r/{subreddit} (limit={limit}, time_filter=day)...")
            stats = process_reddit_articles(
                subreddit_name=subreddit,
                limit=limit,
                time_filter="day"
            )
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
            print(f"Completed r/{subreddit}: external links {stats['external_links']}, queued {stats['queued_links']}")

        print("\nAll subreddits completed. Total Reddit stats:")
        print(f"  Total posts found: {total_stats['total_posts']}")
        print(f"  External links: {total_stats['external_links']}")
        print(f"  Queued links: {total_stats['queued_links']}")
        print(f"  Errors: {total_stats['errors']}")

        queue_stats = get_queue_stats()
        if queue_stats.get("pending_tasks", 0) > 0:
            print(f"\nFound {queue_stats['pending_tasks']} pending summarization tasks.")
            print("Draining queue...")
            drain_queue()
            print("Queue processing completed.")
        else:
            print("\nNo pending tasks in queue.")

        # Show all articles if requested
        if args.show_articles:
            print("\n" + "=" * 60)
            print("ARTICLES AND SUMMARIES")
            print("=" * 60)
            articles = db.query(Articles).order_by(Articles.scraped_date.desc()).all()
            if not articles:
                print("No articles found in the database.")
                return 0

            print(f"\nFound {len(articles)} articles:\n")
            for i, article in enumerate(articles, 1):
                print(f"Article {i}:")
                print(f"  Title: {article.title}")
                print(f"  URL: {article.url}")
                print(f"  Status: {article.status.value}")
                print(f"  Scraped Date: {article.scraped_date}")
                print(f"  Author: {article.author or 'Unknown'}")
                print(f"  Source: {article.source or 'Unknown'}")
                if article.short_summary:
                    print(f"  Short Summary: {article.short_summary}")
                if article.detailed_summary:
                    if article.detailed_summary != article.short_summary:
                        print(f"  Detailed Summary: {article.detailed_summary[:200]}...")
                if article.summary_date:
                    print(f"  Summary Date: {article.summary_date}")
                if not article.short_summary and not article.detailed_summary:
                    print("  No summary available")
                print("-" * 40)
        else:
            print("\nUse --show-articles to display all processed articles.")
            print("Use --clear-existing to clear the database before Reddit scraper.")

    except Exception as e:
        print(f"Error running unified scrapers: {e}")
        return 1

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
