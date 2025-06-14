#!/usr/bin/env python3
"""
Unified test script for the new scraper architecture.
This script has been updated to use the full pipeline with task queue system.
For legacy compatibility, it maintains the same command-line interface.
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import setup_logging, get_logger
from app.core.db import init_db, get_db
from app.core.settings import get_settings
from app.services.queue import get_queue_service, TaskType, TaskStatus
from app.pipeline.task_processor import TaskProcessorPool
from app.scraping.runner import ScraperRunner
from app.models.schema import Content, ProcessingTask, ContentStatus, ContentType
from scripts.run_unified_pipeline import UnifiedPipeline
from sqlalchemy import func

logger = get_logger(__name__)
settings = get_settings()

async def main():
    parser = argparse.ArgumentParser(description="Unified Scrapers Script - Full Pipeline Implementation")
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
        "--use-legacy",
        action="store_true",
        help="Use legacy direct execution instead of task queue"
    )
    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level)

    logger.info("=" * 60)
    logger.info("Unified Scrapers Script - Full Pipeline")
    logger.info("=" * 60)
    logger.info(f"Mode: {'Legacy' if args.use_legacy else 'Task Queue'}")

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    try:
        # Create pipeline instance
        pipeline = UnifiedPipeline()
        queue_service = get_queue_service()
        
        # Show initial statistics
        if args.show_stats:
            initial_stats = pipeline.get_pipeline_stats()
            pipeline.display_stats(initial_stats)
        
        # Show available scrapers
        available_scrapers = pipeline.scraper_runner.list_scrapers()
        logger.info(f"Available scrapers: {', '.join(available_scrapers)}")
        
        # PHASE 1: SCRAPING
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: SCRAPING")
        logger.info("=" * 60)
        
        if args.use_legacy:
            # Legacy mode: Run scrapers directly
            scraper_runner = ScraperRunner()
            if args.scrapers:
                scraper_results = {}
                for scraper_name in args.scrapers:
                    logger.info(f"Running {scraper_name} scraper...")
                    count = await scraper_runner.run_scraper(scraper_name)
                    scraper_results[scraper_name] = count or 0
            else:
                logger.info("Running all scrapers...")
                scraper_results = await scraper_runner.run_all()
            
            total_scraped = sum(scraper_results.values())
            logger.info(f"\nScraping completed. Results:")
            for scraper, count in scraper_results.items():
                logger.info(f"  {scraper}: {count} items")
            logger.info(f"  Total: {total_scraped} items")
        else:
            # New mode: Enqueue scraper tasks
            scraper_count = await pipeline.enqueue_scrapers(args.scrapers)
            logger.info(f"Enqueued {scraper_count} scraper tasks")
            
            # Process scraper tasks
            if scraper_count > 0:
                logger.info("Processing scraper tasks...")
                processor_pool = TaskProcessorPool(max_workers=max(args.max_workers, len(available_scrapers)))
                processor_pool.run_pool()
        
        # Check results
        with get_db() as db:
            content_type_filter = ContentType(args.content_type) if args.content_type else None
            
            query = db.query(Content).filter(Content.status == ContentStatus.NEW.value)
            if content_type_filter:
                query = query.filter(Content.content_type == content_type_filter.value)
            
            available_count = query.count()
            logger.info(f"\nFound {available_count} items available for processing")
            
            if available_count == 0:
                logger.info("No items to process. Exiting.")
                return 0
        
        # PHASE 2: CONTENT PROCESSING
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 2: CONTENT PROCESSING")
        logger.info("=" * 60)
        
        logger.info(f"Content type filter: {args.content_type or 'all'}")
        logger.info(f"Max items: {args.max_items or 'no limit'}")
        
        if args.use_legacy:
            # Legacy mode: Use WorkerPool directly
            from app.pipeline.worker import WorkerPool
            worker_pool = WorkerPool(max_workers=args.max_workers)
            
            logger.info(f"Starting content processing with {args.max_workers} workers...")
            worker_pool.run_workers(
                content_type=ContentType(args.content_type) if args.content_type else None,
                max_items=args.max_items
            )
        else:
            # New mode: Process all pending tasks
            logger.info(f"Processing all pending tasks with {args.max_workers} workers...")
            
            # Get pending task count
            stats = queue_service.get_queue_stats()
            pending_total = sum(stats.get('pending_by_type', {}).values())
            
            if pending_total > 0:
                logger.info(f"Found {pending_total} pending tasks")
                processor_pool = TaskProcessorPool(max_workers=args.max_workers)
                processor_pool.run_pool()
            else:
                logger.info("No pending tasks in queue")
        
        # Show final statistics
        if args.show_stats:
            logger.info("\n" + "=" * 60)
            logger.info("FINAL STATISTICS")
            logger.info("=" * 60)
            
            if args.use_legacy:
                # Legacy stats
                with get_db() as db:
                    # Count by status
                    for status in ContentStatus:
                        count = db.query(Content).filter(Content.status == status.value).count()
                        logger.info(f"  {status.value}: {count}")
                    
                    # Count by type
                    for content_type in ContentType:
                        count = db.query(Content).filter(Content.content_type == content_type.value).count()
                        logger.info(f"  {content_type.value}s: {count}")
                    
                    # Recent activity
                    today = datetime.utcnow().date()
                    processed_today = db.query(Content).filter(
                        Content.processed_at >= today
                    ).count()
                    logger.info(f"  Processed today: {processed_today}")
            else:
                # New comprehensive stats
                final_stats = pipeline.get_pipeline_stats()
                pipeline.display_stats(final_stats)
        
        logger.info("\nUnified scraper pipeline completed successfully!")
        return 0
        
    except KeyboardInterrupt:
        logger.warning("\nProcess interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Error running unified scrapers: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)