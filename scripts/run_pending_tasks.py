#!/usr/bin/env python3
"""
Script to run pending tasks using the sequential task processor.
"""

import argparse
import os
import sys

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import init_db
from app.core.logging import get_logger, setup_logging
from app.pipeline.sequential_task_processor import SequentialTaskProcessor
from app.services.queue import get_queue_service

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Process pending tasks")
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Maximum number of tasks to process (default: unlimited)"
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
    logger.info("Processing Pending Tasks")
    logger.info("=" * 60)
    
    # Initialize database
    logger.info("Initializing database...")
    init_db()
    
    # Check pending tasks
    queue_service = get_queue_service()
    stats = queue_service.get_queue_stats()
    pending_total = sum(stats.get('pending_by_type', {}).values())
    
    if pending_total == 0:
        logger.info("No pending tasks to process")
        return 0
        
    logger.info(f"Found {pending_total} pending tasks:")
    for task_type, count in stats.get('pending_by_type', {}).items():
        logger.info(f"  {task_type}: {count}")
    
    # Run sequential processor
    logger.info("Starting sequential task processor...")
    if args.max_tasks:
        logger.info(f"Will process up to {args.max_tasks} tasks")
    processor = SequentialTaskProcessor()
    
    try:
        processor.run(max_tasks=args.max_tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        processor.running = False
        
    return 0


if __name__ == "__main__":
    sys.exit(main())