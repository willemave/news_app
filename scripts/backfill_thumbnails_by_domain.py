#!/usr/bin/env python3
"""Backfill screenshot thumbnails for news items matching a domain.

Usage:
    python scripts/backfill_thumbnails_by_domain.py --domain example.com --dry-run
    python scripts/backfill_thumbnails_by_domain.py --domain example.com --include-existing
    python scripts/backfill_thumbnails_by_domain.py --domain example.com --days-back 30
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

NEWS_THUMBNAILS_DIR = Path("static/images/news_thumbnails")


def _matches_domain(url: str | None, domain: str) -> bool:
    if not url:
        return False
    return domain.lower() in url.lower()


def _extract_candidate_urls(metadata: dict) -> list[str]:
    urls: list[str] = []
    article_section = metadata.get("article")
    if isinstance(article_section, dict):
        url = article_section.get("url")
        if isinstance(url, str):
            urls.append(url)

    summary_section = metadata.get("summary")
    if isinstance(summary_section, dict):
        final_url = summary_section.get("final_url_after_redirects")
        if isinstance(final_url, str):
            urls.append(final_url)

    return urls


def backfill_thumbnails(
    domain: str,
    dry_run: bool = False,
    limit: int | None = None,
    days_back: float | None = None,
    skip_existing: bool = True,
) -> None:
    """Enqueue thumbnail generation tasks for news content matching a domain.

    Args:
        domain: Domain substring to match in URLs.
        dry_run: Show what would be enqueued without making changes.
        limit: Maximum number of items to enqueue.
        days_back: Number of days to look back. None for no cutoff.
        skip_existing: Skip content that already has generated thumbnails.
    """
    cutoff_date = None
    if days_back is not None:
        cutoff_date = datetime.now(UTC) - timedelta(days=days_back)

    print("Starting news thumbnail backfill")
    print(f"  domain={domain}")
    print(f"  dry_run={dry_run}")
    print(f"  limit={limit}")
    print(f"  days_back={days_back}")
    print(f"  skip_existing={skip_existing}")
    print()

    NEWS_THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

    queue_service = QueueService()

    with get_db() as db:
        query = db.query(Content).filter(
            and_(
                Content.status == ContentStatus.COMPLETED.value,
                Content.content_type == "news",
            )
        )

        if cutoff_date is not None:
            cutoff_date_naive = cutoff_date.replace(tzinfo=None)
            query = query.filter(Content.created_at >= cutoff_date_naive)

        query = query.order_by(Content.created_at.desc())
        if limit:
            query = query.limit(limit)

        content_items = query.all()
        print(f"Found {len(content_items)} completed news items")

        enqueued = 0
        skipped_existing = 0
        skipped_no_match = 0
        skipped_no_summary = 0

        for content in content_items:
            metadata = content.content_metadata or {}

            candidate_urls = [str(content.url)] if content.url else []
            if isinstance(metadata, dict):
                candidate_urls.extend(_extract_candidate_urls(metadata))

            if not any(_matches_domain(url, domain) for url in candidate_urls):
                skipped_no_match += 1
                continue

            if skip_existing and (NEWS_THUMBNAILS_DIR / f"{content.id}.png").exists():
                skipped_existing += 1
                continue

            if not (metadata or {}).get("summary"):
                skipped_no_summary += 1
                continue

            if dry_run:
                title = (content.title or "No title")[:50]
                print(f"  Would enqueue: {content.id} - {title}")
                enqueued += 1
            else:
                task_id = queue_service.enqueue(
                    task_type=TaskType.GENERATE_THUMBNAIL,
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
        print(f"  Skipped (no domain match): {skipped_no_match}")
        print(f"  Skipped (already has thumbnail): {skipped_existing}")
        print(f"  Skipped (no summary): {skipped_no_summary}")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill screenshot thumbnails for news content matching a domain"
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Domain substring to match (e.g., example.com)",
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
        default=None,
        help="Number of days to look back (default: no cutoff)",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Regenerate thumbnails even if they already exist",
    )

    args = parser.parse_args()

    backfill_thumbnails(
        domain=args.domain,
        dry_run=args.dry_run,
        limit=args.limit,
        days_back=args.days_back,
        skip_existing=not args.include_existing,
    )


if __name__ == "__main__":
    main()
