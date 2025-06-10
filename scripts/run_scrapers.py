#!/usr/bin/env python3
"""
Unified test script for HackerNews and Reddit scrapers.
Always runs both scrapers. Supports Reddit flags for clearing existing data and showing results.
"""

import sys
import os
import argparse
import logging

# Add parent directory so we can import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.scraping.hackernews_scraper import process_hackernews_articles
from app.scraping.reddit import process_reddit_articles, validate_reddit_config
from app.scraping.substack_scraper import run_substack_scraper
from app.models import Articles, Links, LinkStatus
from scripts.process_local_articles import process_new_local_articles
from app.database import SessionLocal, init_db
from app.links.pipeline_orchestrator import LinkPipelineOrchestrator
from app.config import setup_logging, logger

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
    parser.add_argument(
        "--processors",
        type=int,
        default=3,
        help="Number of concurrent link processors (default: 3)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    args = parser.parse_args()

    # Setup logging
    if args.debug:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.INFO)

    logger.info("=" * 60)
    logger.info("Unified Scrapers Test Script")
    logger.info("=" * 60)

    logger.info("Initializing database...")
    init_db()
    db = SessionLocal()

    try:
        if args.clear_existing:
            logger.info("Clearing ALL existing articles from the database (due to --clear-existing)...")
            db.query(Articles).delete()
            db.commit()
            logger.info("All existing articles cleared.")

        # HackerNews scraper
        logger.info("\n" + "=" * 60)
        logger.info("HackerNews Scraper")
        logger.info("=" * 60)

        logger.info("Running HackerNews scraper...")
        hn_stats = process_hackernews_articles()
        logger.info("\nHackerNews stats:")
        logger.info(f"  Total links found: {hn_stats['total_links']}")
        logger.info(f"  New links created: {hn_stats['queued_links']}")
        logger.info(f"  Errors: {hn_stats['errors']}")

        # Reddit scraper
        logger.info("\n" + "=" * 60)
        logger.info("Reddit Scraper")
        logger.info("=" * 60)

        if not validate_reddit_config():
            logger.error("Reddit API configuration is incomplete.")
            logger.error("Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT.")
            return 1

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

        logger.info("\nAll subreddits completed. Total Reddit stats:")
        logger.info(f"  Total posts found: {total_stats['total_posts']}")
        logger.info(f"  External links: {total_stats['external_links']}")
        logger.info(f"  New links created: {total_stats['queued_links']}")
        logger.info(f"  Errors: {total_stats['errors']}")

        # Substack scraper
        logger.info("\n" + "=" * 60)
        logger.info("Substack Scraper")
        logger.info("=" * 60)
        run_substack_scraper()
        logger.info("Substack scraper finished.")

        # Process local articles (from Substack)
        logger.info("Processing newly downloaded local articles...")
        process_new_local_articles(db)
        logger.info("Local article processing finished.")

        # Process all links using the new pipeline orchestrator
        logger.info("\n" + "=" * 60)
        logger.info("LINK PROCESSING PIPELINE")
        logger.info("=" * 60)
        
        # Count available links for processing
        new_links_count = db.query(Links).filter(Links.status == LinkStatus.new).count()
        logger.info(f"Found {new_links_count} new links to process")
        
        if new_links_count > 0:
            logger.info(f"Starting link processing pipeline with {args.processors} concurrent processors...")
            
            # Initialize and run the pipeline orchestrator
            orchestrator = LinkPipelineOrchestrator(processor_concurrency=args.processors)
            
            try:
                orchestrator.run()
                
                # Get final statistics
                final_status = orchestrator.get_status()
                stats = final_status['statistics']
                
                logger.info(f"\nLink processing pipeline completed:")
                logger.info(f"  Cycles completed: {stats['cycles_completed']}")
                logger.info(f"  Links processed: {stats['links_processed']}")
                logger.info(f"  Links skipped: {stats['links_skipped']}")
                logger.info(f"  Links failed: {stats['links_failed']}")
                logger.info(f"  Total processed: {stats['total_processed']}")
                
            except KeyboardInterrupt:
                logger.warning("\nLink processing interrupted by user")
                orchestrator.shutdown()
            except Exception as e:
                logger.error(f"Error in link processing pipeline: {e}", exc_info=True)
                orchestrator.shutdown()
        else:
            logger.info("No new links to process.")

        # Show all articles if requested
        if args.show_articles:
            logger.info("\n" + "=" * 60)
            logger.info("ARTICLES AND SUMMARIES")
            logger.info("=" * 60)
            articles = db.query(Articles).order_by(Articles.scraped_date.desc()).all()
            if not articles:
                logger.info("No articles found in the database.")
                return 0

            logger.info(f"\nFound {len(articles)} articles:\n")
            for i, article in enumerate(articles, 1):
                logger.info(f"Article {i}:")
                logger.info(f"  Title: {article.title}")
                logger.info(f"  URL: {article.url}")
                logger.info(f"  Status: {article.status.value}")
                logger.info(f"  Scraped Date: {article.scraped_date}")
                logger.info(f"  Author: {article.author or 'Unknown'}")
                logger.info(f"  Source: {article.source or 'Unknown'}")
                if article.short_summary:
                    logger.info(f"  Short Summary: {article.short_summary}")
                if article.detailed_summary:
                    if article.detailed_summary != article.short_summary:
                        logger.info(f"  Detailed Summary: {article.detailed_summary[:200]}...")
                if article.summary_date:
                    logger.info(f"  Summary Date: {article.summary_date}")
                if not article.short_summary and not article.detailed_summary:
                    logger.info("  No summary available")
                logger.info("-" * 40)
        else:
            logger.info("\nUse --show-articles to display all processed articles.")
            logger.info("Use --clear-existing to clear the database before Reddit scraper.")
            logger.info("Use --processors N to set number of concurrent link processors.")

    except Exception as e:
        logger.error(f"Error running unified scrapers: {e}", exc_info=True)
        return 1

    finally:
        db.close()

    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
