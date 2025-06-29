#!/usr/bin/env python3
"""
Run workers using the sequential task processor.
"""

import sys
import os
import argparse
import time

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import setup_logging, get_logger
from app.core.db import init_db
from app.pipeline.sequential_task_processor import SequentialTaskProcessor
from app.services.queue import get_queue_service

logger = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run sequential task processor")
    parser.add_argument(
        "--max-tasks",
        type=int,
        default=None,
        help="Maximum number of tasks to process (default: unlimited)",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--stats-interval",
        type=int,
        default=30,
        help="Show stats every N seconds (default: 30, 0 to disable)",
    )
    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level)

    logger.info("=" * 60)
    logger.info("Sequential Task Processor")
    logger.info("=" * 60)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Check initial queue stats
    queue_service = get_queue_service()
    stats = queue_service.get_queue_stats()
    pending_total = sum(stats.get("pending_by_type", {}).values())

    by_status = stats.get("by_status", {})
    logger.info(f"Initial queue state:")
    logger.info(f"  Total tasks: {sum(by_status.values())}")
    logger.info(f"  Pending: {by_status.get('pending', 0)}")
    logger.info(f"  Processing: {by_status.get('processing', 0)}")
    logger.info(f"  Completed: {by_status.get('completed', 0)}")
    logger.info(f"  Failed: {by_status.get('failed', 0)}")

    if pending_total > 0:
        logger.info(f"\nPending tasks by type:")
        for task_type, count in stats.get("pending_by_type", {}).items():
            logger.info(f"  {task_type}: {count}")

    # Start processor
    logger.info(f"\nStarting sequential task processor...")
    if args.max_tasks:
        logger.info(f"Will process up to {args.max_tasks} tasks")
    logger.info("Press Ctrl+C to stop")

    logger.debug("Creating SequentialTaskProcessor instance...")
    processor = SequentialTaskProcessor()
    logger.debug("SequentialTaskProcessor instance created")

    # Start stats thread if enabled
    stats_thread = None
    if args.stats_interval > 0:
        import threading

        def show_stats():
            while processor.running:
                time.sleep(args.stats_interval)
                if processor.running:
                    stats = queue_service.get_queue_stats()
                    pending = sum(stats.get("pending_by_type", {}).values())
                    by_status = stats.get("by_status", {})
                    logger.info(
                        f"Queue stats - Pending: {pending}, Completed: {by_status.get('completed', 0)}, Failed: {by_status.get('failed', 0)}"
                    )

        stats_thread = threading.Thread(target=show_stats, daemon=True)
        stats_thread.start()

    try:
        logger.debug("Calling processor.run()...")
        processor.run(max_tasks=args.max_tasks)
    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
        processor.running = False

        # Show final stats
        time.sleep(1)  # Let workers finish
        final_stats = queue_service.get_queue_stats()
        final_by_status = final_stats.get("by_status", {})
        logger.info("\nFinal queue stats:")
        logger.info(f"  Completed: {final_by_status.get('completed', 0)}")
        logger.info(f"  Failed: {final_by_status.get('failed', 0)}")
        logger.info(f"  Remaining: {sum(final_stats.get('pending_by_type', {}).values())}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
