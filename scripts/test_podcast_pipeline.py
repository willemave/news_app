#!/usr/bin/env python3
"""Test script for podcast scraping and processing pipeline."""

import sys
import os
from datetime import datetime

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import setup_logging, get_logger
from app.core.db import init_db, get_db
from app.services.queue import get_queue_service, TaskType
from app.pipeline.sequential_task_processor import SequentialTaskProcessor
from app.scraping.runner import ScraperRunner
from app.models.schema import Content, ProcessingTask
from app.models.metadata import ContentStatus, ContentType
from sqlalchemy import func

logger = get_logger(__name__)


def main():
    """Main test function."""
    # Setup logging
    setup_logging(level="INFO")
    
    logger.info("=" * 60)
    logger.info("Podcast Processing Test Pipeline")
    logger.info("=" * 60)
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    try:
        # Create services
        queue_service = get_queue_service()
        scraper_runner = ScraperRunner()
        
        # Show initial stats
        with get_db() as db:
            podcast_count = db.query(Content).filter(
                Content.content_type == ContentType.PODCAST.value
            ).count()
            logger.info(f"Initial podcast count: {podcast_count}")
        
        # PHASE 1: SCRAPING
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 1: PODCAST SCRAPING")
        logger.info("=" * 60)
        
        logger.info("Running podcast scraper...")
        stats = scraper_runner.run_scraper_with_stats("podcast")
        
        if stats:
            logger.info(f"Scraping results:")
            logger.info(f"  Scraped: {stats.scraped}")
            logger.info(f"  Saved: {stats.saved}")
            logger.info(f"  Duplicates: {stats.duplicates}")
            logger.info(f"  Errors: {stats.errors}")
        else:
            logger.error("Failed to run podcast scraper")
            return 1
        
        # Check what podcast content is available
        with get_db() as db:
            # Find NEW podcast contents
            new_podcasts = db.query(Content).filter(
                Content.content_type == ContentType.PODCAST.value,
                Content.status == ContentStatus.NEW.value
            ).all()
            
            logger.info(f"\nFound {len(new_podcasts)} NEW podcast items")
            
            if not new_podcasts:
                logger.info("No new podcasts to process. Checking for incomplete ones...")
                
                # Find podcasts that need processing
                need_processing = []
                
                all_podcasts = db.query(Content).filter(
                    Content.content_type == ContentType.PODCAST.value
                ).limit(20).all()
                
                for podcast in all_podcasts:
                    metadata = podcast.content_metadata or {}
                    if metadata.get("audio_url") and not metadata.get("transcript"):
                        need_processing.append(podcast)
                
                logger.info(f"Found {len(need_processing)} podcasts that need processing")
                
                # Show a few examples
                for podcast in need_processing[:3]:
                    metadata = podcast.content_metadata or {}
                    logger.info(f"  - {podcast.title}")
                    logger.info(f"    Status: {podcast.status}")
                    logger.info(f"    Has audio_url: {'Yes' if metadata.get('audio_url') else 'No'}")
                    logger.info(f"    Has file_path: {'Yes' if metadata.get('file_path') else 'No'}")
                    logger.info(f"    Has transcript: {'Yes' if metadata.get('transcript') else 'No'}")
                
                if not need_processing:
                    logger.info("All podcasts are fully processed!")
                    return 0
                
                # Create tasks for podcasts that need processing
                logger.info("\nCreating processing tasks for incomplete podcasts...")
                tasks_created = 0
                for podcast in need_processing[:5]:  # Limit to 5 for testing
                    task_id = queue_service.enqueue(
                        task_type=TaskType.PROCESS_CONTENT,
                        content_id=podcast.id
                    )
                    if task_id:
                        tasks_created += 1
                        logger.info(f"  Created task for: {podcast.title}")
            else:
                # Create processing tasks for NEW podcasts
                logger.info("Creating processing tasks for NEW podcasts...")
                tasks_created = 0
                for podcast in new_podcasts[:5]:  # Limit to 5 for testing
                    task_id = queue_service.enqueue(
                        task_type=TaskType.PROCESS_CONTENT,
                        content_id=podcast.id
                    )
                    if task_id:
                        tasks_created += 1
                
                logger.info(f"Created {tasks_created} processing tasks")
        
        # PHASE 2: CONTENT PROCESSING
        logger.info("\n" + "=" * 60)
        logger.info("PHASE 2: PODCAST PROCESSING")
        logger.info("=" * 60)
        
        # Get pending task count
        stats = queue_service.get_queue_stats()
        pending_tasks = sum(stats.get('pending_by_type', {}).values())
        
        if pending_tasks > 0:
            logger.info(f"Found {pending_tasks} pending tasks")
            logger.info("Starting sequential task processor...")
            
            processor = SequentialTaskProcessor()
            # Process up to 5 tasks for testing
            processor.run(max_tasks=5)
            
            # Show results
            logger.info("\n" + "=" * 60)
            logger.info("PROCESSING RESULTS")
            logger.info("=" * 60)
            
            with get_db() as db:
                # Count processed podcasts
                processed_count = 0
                transcribed_count = 0
                failed_count = 0
                
                podcasts = db.query(Content).filter(
                    Content.content_type == ContentType.PODCAST.value
                ).limit(20).all()
                
                for podcast in podcasts:
                    metadata = podcast.content_metadata or {}
                    if podcast.status == ContentStatus.FAILED.value:
                        failed_count += 1
                        logger.error(f"Failed: {podcast.title} - {podcast.error_message}")
                    elif metadata.get("file_path"):
                        processed_count += 1
                        if metadata.get("transcript"):
                            transcribed_count += 1
                
                logger.info(f"Total podcasts: {len(podcasts)}")
                logger.info(f"Downloaded: {processed_count}")
                logger.info(f"Transcribed: {transcribed_count}")
                logger.info(f"Failed: {failed_count}")
                
                # Show some successful examples
                if transcribed_count > 0:
                    logger.info("\nSuccessfully transcribed podcasts:")
                    for podcast in podcasts:
                        metadata = podcast.content_metadata or {}
                        if metadata.get("transcript"):
                            transcript = metadata["transcript"]
                            logger.info(f"  - {podcast.title}")
                            logger.info(f"    Length: {len(transcript)} chars")
                            logger.info(f"    Preview: {transcript[:150]}...")
                            break  # Just show one example
        else:
            logger.info("No pending tasks to process")
        
        logger.info("\nPipeline test completed!")
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