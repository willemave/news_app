#!/usr/bin/env python3
"""
Scheduled scraper job that runs HackerNews and Reddit scrapers on an hourly basis.
"""
import schedule
import time
import logging
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db
from app.scraping.hackernews_scraper import process_hackernews_articles
from app.scraping.reddit import process_reddit_articles
from app.config import logger

# Initialize database to ensure tables exist
init_db()

def run_all():
    """Run all scrapers and log the results."""
    logger.info("Running scheduled scrapers job")
    
    try:
        # Run HackerNews scraper
        logger.info("Starting HackerNews scraper")
        hn_stats = process_hackernews_articles()
        logger.info(f"HackerNews scraper completed: {hn_stats}")
        
        # Run Reddit front page scraper (uses SUBREDDIT_LIMITS for limit)
        logger.info("Starting Reddit front page scraper")
        reddit_stats = process_reddit_articles("front")
        logger.info(f"Reddit front page scraper completed: {reddit_stats}")
        
        logger.info("All scrapers completed successfully")
        
    except Exception as e:
        logger.error(f"Error in scheduled scraper job: {e}", exc_info=True)

def main():
    """Main function to set up scheduling and run the job loop."""
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

if __name__ == "__main__":
    main()