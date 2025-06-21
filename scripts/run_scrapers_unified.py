#!/usr/bin/env python3
"""
Unified test script for running scrapers with the new ProcessingTask queue system.
This script runs scrapers and then processes content using the task queue.
"""

import sys
import os
import argparse
from datetime import datetime

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import setup_logging, get_logger
from app.core.db import init_db, get_db
from app.core.settings import get_settings
from app.services.queue import get_queue_service, TaskType
from app.services.event_logger import track_event, log_event
from app.pipeline.sequential_task_processor import SequentialTaskProcessor
from app.scraping.runner import ScraperRunner
from app.models.schema import Content, ProcessingTask
from app.models.metadata import ContentStatus, ContentType
from sqlalchemy import func

logger = get_logger(__name__)
settings = get_settings()

def main():
    parser = argparse.ArgumentParser(description="Run scrapers and process content using the new task queue system")
    parser.add_argument(
        "--scrapers",
        nargs="*",
        help="Specific scrapers to run (e.g., hackernews reddit). If not specified, runs all."
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=3,
        help="Number of concurrent task processors (default: 3)"
    )
    parser.add_argument(
        "--max-items",
        type=int,
        help="Maximum items to process (default: no limit)"
    )
    parser.add_argument(
        "--content-type",
        choices=["article", "podcast"],
        help="Filter processing by content type"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    parser.add_argument(
        "--show-stats",
        action="store_true",
        help="Show detailed statistics after processing"
    )
    parser.add_argument(
        "--skip-scraping",
        action="store_true",
        help="Skip scraping phase and only process existing content"
    )
    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level)

    logger.info("=" * 60)
    logger.info("Scrapers and Processing Pipeline")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    try:
        # Create services
        queue_service = get_queue_service()
        scraper_runner = ScraperRunner()
        
        # Show initial statistics
        if args.show_stats:
            stats = queue_service.get_queue_stats()
            logger.info(f"Initial queue stats: {stats}")
        
        # Determine run type
        if args.scrapers:
            # If specific scrapers are provided, use the first one as run type
            # or 'custom' if multiple
            run_type = args.scrapers[0] if len(args.scrapers) == 1 else 'custom'
        else:
            run_type = 'all'
        
        # Create run configuration
        run_config = {
            "max_workers": args.max_workers,
            "content_types": [args.content_type] if args.content_type else None,
            "debug": args.debug,
            "specific_scrapers": args.scrapers
        }
        
        # Start tracking the scraper run
        with track_event("scraper_run", run_type, config=run_config) as event_id:
        
            # PHASE 1: SCRAPING (unless skipped)
            if not args.skip_scraping:
                logger.info("\n" + "=" * 60)
                logger.info("PHASE 1: SCRAPING")
                logger.info("=" * 60)
                
                # Show available scrapers
                available_scrapers = scraper_runner.list_scrapers()
                logger.info(f"Available scrapers: {', '.join(available_scrapers)}")
                
                # Run scrapers
                if args.scrapers:
                    scraper_results = {}
                    scraper_stats = {}
                    for scraper_name in args.scrapers:
                        logger.info(f"Running {scraper_name} scraper...")
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
                                errors=stats.errors
                            )
                        else:
                            scraper_results[scraper_name] = 0
                else:
                    logger.info("Running all scrapers...")
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
                        scraper_stats={name: {"scraped": s.scraped, "saved": s.saved, "duplicates": s.duplicates, "errors": s.errors} for name, s in scraper_stats.items()}
                    )
                
                total_scraped = sum(scraper_results.values())
                logger.info(f"\nScraping completed. Results:")
                for scraper, count in scraper_results.items():
                    logger.info(f"  {scraper}: {count} items")
                logger.info(f"  Total: {total_scraped} items")
        
            # Check what content is available for processing
            with get_db() as db:
                content_type_filter = ContentType(args.content_type) if args.content_type else None
                
                query = db.query(Content).filter(Content.status == ContentStatus.NEW.value)
                if content_type_filter:
                    query = query.filter(Content.content_type == content_type_filter.value)
                
                available_count = query.count()
                logger.info(f"\nFound {available_count} NEW items available for processing")
                
                if available_count == 0:
                    logger.info("No items to process. Exiting.")
                    return 0
                
                # Create processing tasks for NEW content
                logger.info("Creating processing tasks for NEW content...")
                contents = query.limit(args.max_items if args.max_items else None).all()
                
                tasks_created = 0
                for content in contents:
                    task_id = queue_service.enqueue(
                        task_type=TaskType.PROCESS_CONTENT,
                        content_id=content.id
                    )
                    if task_id:
                        tasks_created += 1
                
                logger.info(f"Created {tasks_created} processing tasks")
        
            # PHASE 2: CONTENT PROCESSING
            logger.info("\n" + "=" * 60)
            logger.info("PHASE 2: CONTENT PROCESSING")
            logger.info("=" * 60)
            
            logger.info(f"Content type filter: {args.content_type or 'all'}")
            logger.info(f"Max items: {args.max_items or 'no limit'}")
            
            # Process all pending tasks
            logger.info(f"Processing all pending tasks with {args.max_workers} workers...")
            
            # Get pending task count before processing
            stats_before = queue_service.get_queue_stats()
            pending_total = sum(stats_before.get('pending_by_type', {}).values())
            
            if pending_total > 0:
                logger.info(f"Found {pending_total} pending tasks")
                processor = SequentialTaskProcessor()
                # Run with max_tasks limit if specified
                processor.run(max_tasks=args.max_items)
                
                # Get stats after processing
                stats_after = queue_service.get_queue_stats()
                
                # Log processing stats
                log_event(
                    event_type="processing_stats",
                    parent_event_id=event_id,
                    queued=stats_before.get('total_tasks', 0),
                    completed=stats_after.get('completed', 0),
                    failed=stats_after.get('failed', 0),
                    pending=sum(stats_after.get('pending_by_type', {}).values())
                )
            else:
                logger.info("No pending tasks in queue")
        
            # Show final statistics
            if args.show_stats:
                logger.info("\n" + "=" * 60)
                logger.info("FINAL STATISTICS")
                logger.info("=" * 60)
            
                # Queue stats
                final_stats = queue_service.get_queue_stats()
                logger.info("Queue Statistics:")
                logger.info(f"  Total tasks: {final_stats.get('total_tasks', 0)}")
                logger.info(f"  Pending: {sum(final_stats.get('pending_by_type', {}).values())}")
                logger.info(f"  Completed: {final_stats.get('completed', 0)}")
                logger.info(f"  Failed: {final_stats.get('failed', 0)}")
            
                # Content stats
                with get_db() as db:
                    logger.info("\nContent Statistics:")
                    # Count by status
                    for status in ContentStatus:
                        count = db.query(Content).filter(Content.status == status.value).count()
                        logger.info(f"  {status.value}: {count}")
                    
                    # Count by type
                    logger.info("\nContent by type:")
                    for content_type in ContentType:
                        count = db.query(Content).filter(Content.content_type == content_type.value).count()
                        logger.info(f"  {content_type.value}s: {count}")
                    
                    # Recent activity
                    today = datetime.utcnow().date()
                    processed_today = db.query(Content).filter(
                        func.date(Content.processed_at) >= today
                    ).count()
                    logger.info(f"\nProcessed today: {processed_today}")
        
            logger.info("\nPipeline completed successfully!")
            return 0
        
    except KeyboardInterrupt:
        logger.warning("\nProcess interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Error running pipeline: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)