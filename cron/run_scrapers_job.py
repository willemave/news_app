#!/usr/bin/env python3
"""
Scheduled scraper job that runs HackerNews and Reddit scrapers on an hourly basis.
Unified test script for HackerNews and Reddit scrapers.
Always runs both scrapers. Supports Reddit flags for clearing existing data and showing results.
"""
import schedule
import time
import logging
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
from app.config import logger

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

# Initialize database to ensure tables exist
init_db()

def run_unified_scrapers(clear_existing: bool = False, show_articles: bool = False):
    """
    Run all scrapers with comprehensive logging and error handling.
    Integrates the complete logic from run_scrapers.py.
    """
    logger.info("=" * 60)
    logger.info("Unified Scrapers Job")
    logger.info("=" * 60)

    logger.info("Initializing database...")
    db = SessionLocal()

    try:
        if clear_existing:
            logger.info("Clearing ALL existing articles from the database (due to clear_existing flag)...")
            db.query(Articles).delete()
            db.commit()
            logger.info("All existing articles cleared.")

        # HackerNews scraper
        logger.info("\n" + "=" * 60)
        logger.info("HackerNews Scraper")
        logger.info("=" * 60)

        logger.info("Running HackerNews scraper...")
        hn_stats = process_hackernews_articles()
        logger.info("HackerNews stats:")
        logger.info(f"  Total links found: {hn_stats['total_links']}")
        logger.info(f"  Queued links: {hn_stats['queued_links']}")
        logger.info(f"  Errors: {hn_stats['errors']}")

        queue_stats = get_queue_stats()
        if queue_stats.get("pending_tasks", 0) > 0:
            logger.info(f"Found {queue_stats['pending_tasks']} pending summarization tasks.")
            logger.info("Draining queue...")
            drain_queue()
            logger.info("Queue processing completed.")
        else:
            logger.info("No pending tasks in queue.")

        # Reddit scraper
        logger.info("\n" + "=" * 60)
        logger.info("Reddit Scraper")
        logger.info("=" * 60)

        if not validate_reddit_config():
            logger.error("ERROR: Reddit API configuration is incomplete.")
            logger.error("Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT.")
            return False

        total_stats = {
            "total_posts": 0,
            "external_links": 0,
            "queued_links": 0,
            "errors": 0
        }

        for subreddit, limit in SUBREDDIT_MAP.items():
            logger.info(f"Running Reddit scraper for r/{subreddit} (limit={limit}, time_filter=day)...")
            stats = process_reddit_articles(
                subreddit_name=subreddit,
                limit=limit,
                time_filter="day"
            )
            for key in total_stats:
                total_stats[key] += stats.get(key, 0)
            logger.info(f"Completed r/{subreddit}: external links {stats['external_links']}, queued {stats['queued_links']}")

        logger.info("All subreddits completed. Total Reddit stats:")
        logger.info(f"  Total posts found: {total_stats['total_posts']}")
        logger.info(f"  External links: {total_stats['external_links']}")
        logger.info(f"  Queued links: {total_stats['queued_links']}")
        logger.info(f"  Errors: {total_stats['errors']}")

        queue_stats = get_queue_stats()
        if queue_stats.get("pending_tasks", 0) > 0:
            logger.info(f"Found {queue_stats['pending_tasks']} pending summarization tasks.")
            logger.info("Draining queue...")
            drain_queue()
            logger.info("Queue processing completed.")
        else:
            logger.info("No pending tasks in queue.")

        logger.info("All scrapers completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error running unified scrapers: {e}", exc_info=True)
        return False

    finally:
        db.close()


def run_all():
    """Run all scrapers and log the results (scheduled job version)."""
    logger.info("Running scheduled scrapers job")
    return run_unified_scrapers(clear_existing=False, show_articles=False)

def run_scheduled_mode():
    """Run in scheduled mode (original functionality)."""
    logger.info("Starting scheduled scraper job service")
    
    # Schedule the job to run every hour
    schedule.every().hour.do(run_all)
    
    # Run immediately on startup
    logger.info("Running initial scraper job")
    run_all()
    
    # Keep the service running
    logger.info("Entering scheduler loop (runs every hour)")
    while True:
        try:
            schedule.run_pending()
            time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down")
            break
        except Exception as e:
            logger.error(f"Error in scheduler loop: {e}", exc_info=True)
            time.sleep(60)  # Wait a minute before retrying


def main():
    """
    Main function that determines execution mode.
    If command-line arguments are provided, run in manual mode.
    Otherwise, run in scheduled mode.
    """
    run_scheduled_mode()


if __name__ == "__main__":
    main()