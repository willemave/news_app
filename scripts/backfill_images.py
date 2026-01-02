#!/usr/bin/env python3
"""Script to backfill AI-generated images for existing content.

Usage:
    python scripts/backfill_images.py --limit 50 --dry-run
    python scripts/backfill_images.py --limit 50 --days-back 14
    python scripts/backfill_images.py --types article podcast
    python scripts/backfill_images.py --include-existing  # Regenerate images
"""

import argparse
import os
import sys
from datetime import UTC, datetime, timedelta

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import and_, exists, select  # noqa: E402

from app.core.db import get_db  # noqa: E402
from app.core.logging import get_logger, setup_logging  # noqa: E402
from app.models.metadata import ContentStatus  # noqa: E402
from app.models.schema import Content, ContentStatusEntry  # noqa: E402
from app.services.queue import QueueService, TaskType  # noqa: E402
from app.utils.image_paths import get_content_images_dir  # noqa: E402

setup_logging()
logger = get_logger(__name__)

# Image storage path
IMAGES_DIR = get_content_images_dir()


def backfill_images(
    dry_run: bool = False,
    limit: int | None = None,
    days_back: float = 7,
    content_types: list[str] | None = None,
    skip_existing: bool = True,
) -> None:
    """Enqueue image generation tasks for content in user inboxes.

    Only processes content that is in at least one user's inbox.

    Args:
        dry_run: Show what would be enqueued without making changes
        limit: Maximum number of items to enqueue
        days_back: Number of days to look back
        content_types: List of content types to process (default: article, podcast)
        skip_existing: Skip content that already has generated images
    """
    # Default to article and podcast (not news)
    if content_types is None:
        content_types = ["article", "podcast"]

    cutoff_date = datetime.now(UTC) - timedelta(days=days_back)

    print("Starting image backfill (inbox content only)")
    print(f"  dry_run={dry_run}")
    print(f"  limit={limit}")
    print(f"  days_back={days_back}")
    print(f"  content_types={content_types}")
    print(f"  skip_existing={skip_existing}")
    print()

    # Ensure images directory exists
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    queue_service = QueueService()

    with get_db() as db:
        # Convert to naive datetime for SQLite compatibility
        cutoff_date_naive = cutoff_date.replace(tzinfo=None)

        # Only process content that is in a user's inbox
        is_in_inbox = exists(
            select(ContentStatusEntry.id).where(
                ContentStatusEntry.content_id == Content.id,
                ContentStatusEntry.status == "inbox",
            )
        )

        query = db.query(Content).filter(
            and_(
                Content.created_at >= cutoff_date_naive,
                Content.status == ContentStatus.COMPLETED.value,
                Content.content_type.in_(content_types),
                is_in_inbox,
            )
        )

        query = query.order_by(Content.created_at.desc())

        if limit:
            query = query.limit(limit)

        content_items = query.all()
        print(f"Found {len(content_items)} completed content items")

        enqueued = 0
        skipped_existing = 0
        skipped_youtube = 0
        skipped_no_summary = 0

        for content in content_items:
            # Skip if image already exists
            if skip_existing and (IMAGES_DIR / f"{content.id}.png").exists():
                skipped_existing += 1
                continue

            # Skip YouTube podcasts with thumbnails
            if content.content_type == "podcast":
                meta = content.content_metadata or {}
                if meta.get("thumbnail_url") or meta.get("video_id"):
                    skipped_youtube += 1
                    continue

            # Skip if no summary
            if not (content.content_metadata or {}).get("summary"):
                skipped_no_summary += 1
                continue

            if dry_run:
                title = (content.title or "No title")[:50]
                print(f"  Would enqueue: [{content.content_type}] {content.id} - {title}")
            else:
                task_id = queue_service.enqueue(
                    task_type=TaskType.GENERATE_IMAGE,
                    content_id=content.id,
                )
                logger.info(
                    "Enqueued image generation task %s for content %s",
                    task_id,
                    content.id,
                )
                enqueued += 1

        print("\nSummary:")
        print(f"  Total content items: {len(content_items)}")
        if dry_run:
            print(f"  Would enqueue for generation: {enqueued}")
        else:
            print(f"  Enqueued for generation: {enqueued}")
        print(f"  Skipped (already has image): {skipped_existing}")
        print(f"  Skipped (YouTube with thumbnail): {skipped_youtube}")
        print(f"  Skipped (no summary): {skipped_no_summary}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill AI-generated images for existing content"
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
        "--types",
        nargs="+",
        choices=["article", "podcast", "news"],
        help="Filter by content type(s)",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Regenerate images even if they already exist",
    )

    args = parser.parse_args()

    backfill_images(
        dry_run=args.dry_run,
        limit=args.limit,
        days_back=args.days_back,
        content_types=args.types,
        skip_existing=not args.include_existing,
    )


if __name__ == "__main__":
    main()
