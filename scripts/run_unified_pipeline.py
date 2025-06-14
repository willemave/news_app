#!/usr/bin/env python3
"""
Unified Pipeline Script - Orchestrates the complete content processing pipeline.
Supports running scrapers, processing content, and handling all task types.
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime, timezone
from typing import Optional, List, Dict

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import setup_logging, get_logger
from app.core.db import init_db, get_db
from app.core.settings import get_settings
from app.services.queue import get_queue_service, TaskType, TaskStatus
from app.pipeline.task_processor import TaskProcessorPool
from app.scraping.runner import ScraperRunner
from app.models.unified import Content, ProcessingTask, ContentStatus, ContentType
from sqlalchemy import func

logger = get_logger(__name__)
settings = get_settings()

class UnifiedPipeline:
    """Orchestrates the complete content processing pipeline."""
    
    def __init__(self):
        self.queue_service = get_queue_service()
        self.scraper_runner = ScraperRunner()
    
    async def enqueue_scrapers(self, scrapers: Optional[List[str]] = None) -> int:
        """
        Enqueue scraper tasks.
        
        Args:
            scrapers: List of scraper names to run (None for all)
            
        Returns:
            Number of scraper tasks enqueued
        """
        available_scrapers = self.scraper_runner.list_scrapers()
        
        if scrapers:
            # Filter to requested scrapers
            scrapers_to_run = [s for s in scrapers if s.lower() in [a.lower() for a in available_scrapers]]
        else:
            scrapers_to_run = available_scrapers
        
        logger.info(f"Enqueueing {len(scrapers_to_run)} scrapers: {', '.join(scrapers_to_run)}")
        
        task_ids = []
        for scraper_name in scrapers_to_run:
            task_id = self.queue_service.enqueue(
                TaskType.SCRAPE,
                payload={'scraper_name': scraper_name}
            )
            task_ids.append(task_id)
            logger.info(f"Enqueued SCRAPE task {task_id} for {scraper_name}")
        
        return len(task_ids)
    
    def enqueue_unprocessed_content(self, content_type: Optional[ContentType] = None, max_items: Optional[int] = None) -> int:
        """
        Enqueue PROCESS_CONTENT tasks for unprocessed content.
        
        Args:
            content_type: Filter by content type
            max_items: Maximum items to enqueue
            
        Returns:
            Number of tasks enqueued
        """
        with get_db() as db:
            query = db.query(Content).filter(Content.status == ContentStatus.NEW.value)
            
            if content_type:
                query = query.filter(Content.content_type == content_type.value)
            
            if max_items:
                query = query.limit(max_items)
            
            contents = query.all()
            
            task_count = 0
            for content in contents:
                # Check if already has a pending task
                existing_task = db.query(ProcessingTask).filter(
                    ProcessingTask.content_id == content.id,
                    ProcessingTask.task_type == TaskType.PROCESS_CONTENT.value,
                    ProcessingTask.status == TaskStatus.PENDING.value
                ).first()
                
                if not existing_task:
                    task_id = self.queue_service.enqueue(
                        TaskType.PROCESS_CONTENT,
                        content_id=content.id
                    )
                    logger.debug(f"Enqueued PROCESS_CONTENT task {task_id} for content {content.id}")
                    task_count += 1
            
            logger.info(f"Enqueued {task_count} PROCESS_CONTENT tasks")
            return task_count
    
    def get_pipeline_stats(self) -> Dict:
        """Get comprehensive pipeline statistics."""
        stats = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'queue': self.queue_service.get_queue_stats(),
            'content': {},
            'tasks': {}
        }
        
        with get_db() as db:
            # Content statistics
            for status in ContentStatus:
                count = db.query(func.count(Content.id)).filter(
                    Content.status == status.value
                ).scalar()
                stats['content'][status.value] = count
            
            # Content by type
            for content_type in ContentType:
                count = db.query(func.count(Content.id)).filter(
                    Content.content_type == content_type.value
                ).scalar()
                stats['content'][f'{content_type.value}_total'] = count
            
            # Task statistics by type and status
            task_stats = db.query(
                ProcessingTask.task_type,
                ProcessingTask.status,
                func.count(ProcessingTask.id)
            ).group_by(
                ProcessingTask.task_type,
                ProcessingTask.status
            ).all()
            
            for task_type, status, count in task_stats:
                if task_type not in stats['tasks']:
                    stats['tasks'][task_type] = {}
                stats['tasks'][task_type][status] = count
        
        return stats
    
    def display_stats(self, stats: Dict):
        """Display pipeline statistics in a formatted way."""
        print("\n" + "=" * 60)
        print("PIPELINE STATISTICS")
        print("=" * 60)
        print(f"Timestamp: {stats['timestamp']}")
        
        print("\nCONTENT STATUS:")
        for status, count in stats['content'].items():
            if not status.endswith('_total'):
                print(f"  {status:12}: {count:6}")
        
        print("\nCONTENT TYPES:")
        print(f"  Articles    : {stats['content'].get('article_total', 0):6}")
        print(f"  Podcasts    : {stats['content'].get('podcast_total', 0):6}")
        
        print("\nQUEUE STATUS:")
        for status, count in stats['queue'].get('by_status', {}).items():
            print(f"  {status:12}: {count:6}")
        
        print("\nPENDING TASKS BY TYPE:")
        for task_type, count in stats['queue'].get('pending_by_type', {}).items():
            print(f"  {task_type:18}: {count:6}")
        
        if stats['tasks']:
            print("\nTASK DETAILS:")
            for task_type, statuses in stats['tasks'].items():
                print(f"  {task_type}:")
                for status, count in statuses.items():
                    print(f"    {status:10}: {count:6}")
        
        print("=" * 60)

async def main():
    parser = argparse.ArgumentParser(
        description="Unified Pipeline - Orchestrates complete content processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run full pipeline (scrape then process)
  python run_unified_pipeline.py --mode full
  
  # Run only scrapers
  python run_unified_pipeline.py --mode scrape --scrapers hackernews reddit
  
  # Process only existing content
  python run_unified_pipeline.py --mode process --content-type article
  
  # Process only queued tasks
  python run_unified_pipeline.py --mode tasks --max-workers 5
  
  # Run continuously
  python run_unified_pipeline.py --mode full --continuous --interval 300
        """
    )
    
    parser.add_argument(
        "--mode",
        choices=["full", "scrape", "process", "tasks"],
        default="full",
        help="Pipeline mode: full (scrape+process), scrape, process, or tasks"
    )
    
    parser.add_argument(
        "--scrapers",
        nargs="*",
        help="Specific scrapers to run (e.g., hackernews reddit). If not specified, runs all."
    )
    
    parser.add_argument(
        "--content-type",
        choices=["article", "podcast"],
        help="Filter processing by content type"
    )
    
    parser.add_argument(
        "--max-workers",
        type=int,
        default=settings.max_workers,
        help=f"Number of concurrent task processors (default: {settings.max_workers})"
    )
    
    parser.add_argument(
        "--max-items",
        type=int,
        help="Maximum items to process (default: no limit)"
    )
    
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously with periodic checks"
    )
    
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Interval in seconds for continuous mode (default: 300)"
    )
    
    parser.add_argument(
        "--show-stats",
        action="store_true",
        default=True,
        help="Show pipeline statistics (default: True)"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level)
    
    logger.info("=" * 60)
    logger.info("UNIFIED PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Mode: {args.mode}")
    logger.info(f"Max workers: {args.max_workers}")
    if args.continuous:
        logger.info(f"Running continuously with {args.interval}s interval")
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    # Create pipeline instance
    pipeline = UnifiedPipeline()
    
    try:
        while True:  # Loop for continuous mode
            logger.info(f"\n{'=' * 60}")
            logger.info(f"PIPELINE RUN - {datetime.now(timezone.utc).isoformat()}")
            logger.info(f"{'=' * 60}")
            
            # Show initial statistics
            if args.show_stats:
                initial_stats = pipeline.get_pipeline_stats()
                pipeline.display_stats(initial_stats)
            
            # Execute based on mode
            if args.mode in ["full", "scrape"]:
                # Enqueue scraper tasks
                logger.info("\nPHASE 1: ENQUEUEING SCRAPERS")
                scraper_count = await pipeline.enqueue_scrapers(args.scrapers)
                logger.info(f"Enqueued {scraper_count} scraper tasks")
            
            if args.mode in ["full", "process"]:
                # Enqueue content processing tasks
                logger.info("\nPHASE 2: ENQUEUEING CONTENT PROCESSING")
                content_type = ContentType(args.content_type) if args.content_type else None
                content_count = pipeline.enqueue_unprocessed_content(
                    content_type=content_type,
                    max_items=args.max_items
                )
                logger.info(f"Enqueued {content_count} content processing tasks")
            
            if args.mode in ["full", "tasks"] or (args.mode == "scrape" and scraper_count > 0) or (args.mode == "process" and content_count > 0):
                # Process tasks
                logger.info(f"\nPHASE 3: PROCESSING TASKS")
                logger.info(f"Starting task processor pool with {args.max_workers} workers")
                
                # Create and run task processor pool
                processor_pool = TaskProcessorPool(max_workers=args.max_workers)
                
                # For non-continuous mode, run until queue is empty
                if not args.continuous:
                    processor_pool.run_pool(max_tasks_per_worker=None)
                else:
                    # For continuous mode, process available tasks then continue
                    processor_pool.run_pool(max_tasks_per_worker=None)
            
            # Show final statistics
            if args.show_stats:
                logger.info("\nFINAL STATISTICS:")
                final_stats = pipeline.get_pipeline_stats()
                pipeline.display_stats(final_stats)
            
            # Break if not continuous mode
            if not args.continuous:
                break
            
            # Wait before next iteration
            logger.info(f"\nSleeping for {args.interval} seconds...")
            await asyncio.sleep(args.interval)
            
    except KeyboardInterrupt:
        logger.warning("\nPipeline interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Pipeline error: {e}", exc_info=True)
        return 1
    
    logger.info("\nUnified pipeline completed successfully!")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)