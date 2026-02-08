#!/usr/bin/env python3
"""
Run workers using the sequential task processor.
"""

import argparse
import os
import sys
import time

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import init_db
from app.core.logging import get_logger, setup_logging
from app.pipeline.sequential_task_processor import SequentialTaskProcessor
from app.services.queue import TaskQueue, get_queue_service

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
    parser.add_argument(
        "--queue",
        choices=[queue.value for queue in TaskQueue],
        default=TaskQueue.CONTENT.value,
        help="Queue partition to process",
    )
    parser.add_argument(
        "--worker-slot",
        type=int,
        default=1,
        help="Worker slot number for stable worker IDs",
    )
    args = parser.parse_args()

    # Setup logging
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(level=log_level)

    logger.info("=" * 60)
    logger.info("Sequential Task Processor")
    logger.info("=" * 60)
    logger.info("Queue: %s", args.queue)
    logger.info("Worker slot: %s", args.worker_slot)

    # Initialize database
    logger.info("Initializing database...")
    init_db()

    # Check initial queue stats
    queue_service = get_queue_service()
    stats = queue_service.get_queue_stats()
    pending_total = stats.get("pending_by_queue", {}).get(args.queue, 0)

    by_status = stats.get("by_status", {})
    logger.info("Initial queue state:")
    logger.info(f"  Total tasks: {sum(by_status.values())}")
    logger.info(f"  Pending: {by_status.get('pending', 0)}")
    logger.info(f"  Processing: {by_status.get('processing', 0)}")
    logger.info(f"  Completed: {by_status.get('completed', 0)}")
    logger.info(f"  Failed: {by_status.get('failed', 0)}")

    queue_pending_by_type = stats.get("pending_by_queue_type", {}).get(args.queue, {})

    if pending_total > 0:
        logger.info("\nPending tasks by type (queue=%s):", args.queue)
        for task_type, count in queue_pending_by_type.items():
            logger.info(f"  {task_type}: {count}")

    # Start processor
    logger.info("\nStarting sequential task processor...")
    if args.max_tasks:
        logger.info(f"Will process up to {args.max_tasks} tasks")
    logger.info("Press Ctrl+C to stop")

    logger.debug("Creating SequentialTaskProcessor instance...")
    processor = SequentialTaskProcessor(queue_name=args.queue, worker_slot=args.worker_slot)
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
                    pending = stats.get("pending_by_queue", {}).get(args.queue, 0)
                    by_status = stats.get("by_status", {})
                    logger.info(
                        "Queue stats (%s) - Pending: %s, Completed: %s, Failed: %s",
                        args.queue,
                        pending,
                        by_status.get("completed", 0),
                        by_status.get("failed", 0),
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
        final_pending = final_stats.get("pending_by_queue", {}).get(args.queue, 0)
        logger.info("\nFinal queue stats:")
        logger.info(f"  Completed: {final_by_status.get('completed', 0)}")
        logger.info(f"  Failed: {final_by_status.get('failed', 0)}")
        logger.info(f"  Remaining in {args.queue}: {final_pending}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
