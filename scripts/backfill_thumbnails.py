#!/usr/bin/env python3
"""Script to backfill AI-generated thumbnails for news content.

Usage:
    python scripts/backfill_thumbnails.py --limit 50 --dry-run
    python scripts/backfill_thumbnails.py --limit 50 --days-back 14
    python scripts/backfill_thumbnails.py --include-existing  # Regenerate thumbnails
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import and_  # noqa: E402

from app.core.db import get_db  # noqa: E402
from app.core.logging import get_logger, setup_logging  # noqa: E402
from app.models.metadata import ContentStatus  # noqa: E402
from app.models.schema import Content  # noqa: E402
from app.services.queue import QueueService, TaskType  # noqa: E402

setup_logging()
logger = get_logger(__name__)

# Thumbnail storage path (matches image_generation.py)
THUMBNAILS_DIR = Path("static/images/news_thumbnails")


def backfill_thumbnails(
    dry_run: bool = False,
    limit: int | None = None,
    days_back: float = 7,
    skip_existing: bool = True,
) -> None:
    """Enqueue thumbnail generation tasks for news content.

    Args:
        dry_run: Show what would be enqueued without making changes
        limit: Maximum number of items to enqueue
        days_back: Number of days to look back
        skip_existing: Skip content that already has generated thumbnails
    """
    cutoff_date = datetime.now(UTC) - timedelta(days=days_back)

    print("Starting news thumbnail backfill")
    print(f"  dry_run={dry_run}")
    print(f"  limit={limit}")
    print(f"  days_back={days_back}")
    print(f"  skip_existing={skip_existing}")
    print()

    # Ensure thumbnails directory exists
    THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

    queue_service = QueueService()

    with get_db() as db:
        # Convert to naive datetime for SQLite compatibility
        cutoff_date_naive = cutoff_date.replace(tzinfo=None)

        # Process all completed news content (news doesn't use inbox workflow)
        query = db.query(Content).filter(
            and_(
                Content.created_at >= cutoff_date_naive,
                Content.status == ContentStatus.COMPLETED.value,
                Content.content_type == "news",
            )
        )

        query = query.order_by(Content.created_at.desc())

        if limit:
            query = query.limit(limit)

        content_items = query.all()
        print(f"Found {len(content_items)} completed news items")

        enqueued = 0
        skipped_existing = 0
        skipped_no_summary = 0

        for content in content_items:
            # Skip if thumbnail already exists
            if skip_existing and (THUMBNAILS_DIR / f"{content.id}.png").exists():
                skipped_existing += 1
                continue

            # Skip if no summary
            if not (content.content_metadata or {}).get("summary"):
                skipped_no_summary += 1
                continue

            if dry_run:
                title = (content.title or "No title")[:50]
                print(f"  Would enqueue: {content.id} - {title}")
                enqueued += 1
            else:
                task_id = queue_service.enqueue(
                    task_type=TaskType.GENERATE_IMAGE,
                    content_id=content.id,
                )
                logger.info(
                    "Enqueued thumbnail generation task %s for news %s",
                    task_id,
                    content.id,
                )
                enqueued += 1

        print("\nSummary:")
        print(f"  Total news items: {len(content_items)}")
        if dry_run:
            print(f"  Would enqueue for generation: {enqueued}")
        else:
            print(f"  Enqueued for generation: {enqueued}")
        print(f"  Skipped (already has thumbnail): {skipped_existing}")
        print(f"  Skipped (no summary): {skipped_no_summary}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill AI-generated thumbnails for news content"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of items to process",
    )
    parser.add_argument(
        "--days-back",
        type=float,
        default=7,
        help="Number of days to look back (default: 7)",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Regenerate thumbnails even if they already exist",
    )

    args = parser.parse_args()

    backfill_thumbnails(
        dry_run=args.dry_run,
        limit=args.limit,
        days_back=args.days_back,
        skip_existing=not args.include_existing,
    )


if __name__ == "__main__":
    main()
