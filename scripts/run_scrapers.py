#!/usr/bin/env python3
"""
Run scrapers to populate content links without processing.
This script only runs the scrapers and saves content to the database.
Use run_workers.py to process the scraped content.
"""

import argparse
import os
import sys
from datetime import UTC, datetime

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func

from app.core.db import get_db, init_db
from app.core.logging import get_logger, setup_logging
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.scraping.runner import ScraperRunner
from app.services.event_logger import log_event, track_event

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run scrapers to populate content links")
    parser.add_argument(
        "--scrapers",
        nargs="*",
        help="Specific scrapers to run (e.g., hackernews reddit). If not specified, runs all.",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--show-stats", action="store_true", help="Show detailed statistics after scraping"
    )
    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level)

    logger.info("=" * 60)
    logger.info("Content Scrapers")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    try:
        # Create scraper runner
        scraper_runner = ScraperRunner()

        # Show initial statistics
        if args.show_stats:
            with get_db() as db:
                total_content = db.query(Content).count()
                new_content = (
                    db.query(Content).filter(Content.status == ContentStatus.NEW.value).count()
                )
                logger.info("Initial database stats:")
                logger.info(f"  Total content: {total_content}")
                logger.info(f"  New content: {new_content}")

        # Determine run type
        if args.scrapers:
            # If specific scrapers are provided, use the first one as run type
            # or 'custom' if multiple
            run_type = args.scrapers[0] if len(args.scrapers) == 1 else "custom"
        else:
            run_type = "all"

        # Create run configuration
        run_config = {"debug": args.debug, "specific_scrapers": args.scrapers}

        # Start tracking the scraper run
        with track_event("scraper_run", run_type, config=run_config) as event_id:
            # Show available scrapers
            available_scrapers = scraper_runner.list_scrapers()
            logger.info(f"Available scrapers: {', '.join(available_scrapers)}")

            # Run scrapers
            if args.scrapers:
                scraper_results = {}
                scraper_stats = {}
                for scraper_name in args.scrapers:
                    logger.info(f"\nRunning {scraper_name} scraper...")
                    stats = scraper_runner.run_scraper_with_stats(scraper_name)
                    if stats:
                        scraper_results[scraper_name] = stats.saved
                        scraper_stats[scraper_name] = stats
                        # Log individual scraper stats
                        log_event(
                            event_type="scraper_summary",
                            event_name=scraper_name,
                            parent_event_id=event_id,
                            scraped=stats.scraped,
                            saved=stats.saved,
                            duplicates=stats.duplicates,
                            errors=stats.errors,
                        )
                        logger.info(
                            "  Scraped: %s, Saved: %s, Duplicates: %s, Errors: %s",
                            stats.scraped,
                            stats.saved,
                            stats.duplicates,
                            stats.errors,
                        )
                    else:
                        scraper_results[scraper_name] = 0
                        logger.warning(f"  No stats returned for {scraper_name}")
            else:
                logger.info("\nRunning all scrapers...")
                scraper_stats = scraper_runner.run_all_with_stats()
                scraper_results = {name: stats.saved for name, stats in scraper_stats.items()}

                # Log summary for all scrapers
                total_scraped = sum(s.scraped for s in scraper_stats.values())
                total_saved = sum(s.saved for s in scraper_stats.values())
                total_duplicates = sum(s.duplicates for s in scraper_stats.values())
                total_errors = sum(s.errors for s in scraper_stats.values())

                log_event(
                    event_type="scraper_run_summary",
                    event_name="all",
                    parent_event_id=event_id,
                    total_scraped=total_scraped,
                    total_saved=total_saved,
                    total_duplicates=total_duplicates,
                    total_errors=total_errors,
                    scraper_stats={
                        name: {
                            "scraped": s.scraped,
                            "saved": s.saved,
                            "duplicates": s.duplicates,
                            "errors": s.errors,
                        }
                        for name, s in scraper_stats.items()
                    },
                )

                # Show individual scraper results
                for scraper_name, stats in scraper_stats.items():
                    logger.info(f"\n{scraper_name}:")
                    logger.info(
                        "  Scraped: %s, Saved: %s, Duplicates: %s, Errors: %s",
                        stats.scraped,
                        stats.saved,
                        stats.duplicates,
                        stats.errors,
                    )

            # Summary
            total_scraped = sum(scraper_results.values())
            logger.info("\n" + "=" * 60)
            logger.info("Scraping completed. Summary:")
            for scraper, count in scraper_results.items():
                logger.info(f"  {scraper}: {count} new items")
            logger.info(f"  Total: {total_scraped} new items")

            # Show final statistics
            if args.show_stats:
                with get_db() as db:
                    logger.info("\n" + "=" * 60)
                    logger.info("FINAL STATISTICS")
                    logger.info("=" * 60)

                    # Content stats
                    logger.info("Content Statistics:")
                    # Count by status
                    for status in ContentStatus:
                        count = db.query(Content).filter(Content.status == status.value).count()
                        logger.info(f"  {status.value}: {count}")

                    # Count by type
                    logger.info("\nContent by type:")
                    for content_type in ContentType:
                        count = (
                            db.query(Content)
                            .filter(Content.content_type == content_type.value)
                            .count()
                        )
                        logger.info(f"  {content_type.value}s: {count}")

                    # Recent activity
                    today = datetime.now(UTC).date()
                    scraped_today = (
                        db.query(Content).filter(func.date(Content.created_at) >= today).count()
                    )
                    logger.info(f"\nScraped today: {scraped_today}")

                    # NEW content ready for processing
                    new_content = (
                        db.query(Content).filter(Content.status == ContentStatus.NEW.value).count()
                    )
                    logger.info(f"\nContent ready for processing: {new_content}")
                    if new_content > 0:
                        logger.info(
                            "Run 'python scripts/run_workers.py' to process the scraped content"
                        )

        logger.info("\nScraping completed successfully!")
        return 0

    except KeyboardInterrupt:
        logger.warning("\nProcess interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Error running scrapers: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
