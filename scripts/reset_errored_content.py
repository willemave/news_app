#!/usr/bin/env python3
"""
Reset errored content for re-processing.
This script:
1. Finds content with 'error' status
2. Optionally filters by date range
3. Resets status to 'new' and clears error data
4. Creates new processing tasks for the content
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path for imports (use os.path for Python 3.13 compatibility)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import get_settings
from app.models.schema import Content, ContentStatus, ProcessingTask


def parse_datetime(value: str) -> datetime:
    """Parse a datetime string in various formats.

    Supports:
        - ISO format: 2024-01-15T10:30:00
        - Date only: 2024-01-15 (assumes start of day)
        - Date and time: 2024-01-15 10:30
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise argparse.ArgumentTypeError(
        f"Invalid datetime format: {value}. Use YYYY-MM-DD or YYYY-MM-DD HH:MM"
    )


def reset_errored_content(
    days: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    dry_run: bool = False,
):
    """Reset errored content for re-processing.

    Args:
        days: Only reset content errored within this many days (None = all errored content)
        since: Only reset content errored on or after this datetime
        until: Only reset content errored before this datetime
        dry_run: If True, show what would be reset without making changes
    """
    # Get database settings
    settings = get_settings()

    # Create engine and session
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    with SessionLocal() as db:
        try:
            # Build query for errored content
            query = db.query(Content).filter(Content.status == ContentStatus.FAILED.value)

            # Add date filters
            if days:
                cutoff_date = datetime.utcnow() - timedelta(days=days)
                query = query.filter(Content.updated_at >= cutoff_date)
                cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
                print(f"Filtering to content errored since {cutoff_str} UTC")
            if since:
                query = query.filter(Content.updated_at >= since)
                since_str = since.strftime("%Y-%m-%d %H:%M:%S")
                print(f"Filtering to content errored on or after {since_str}")
            if until:
                query = query.filter(Content.updated_at < until)
                print(f"Filtering to content errored before {until.strftime('%Y-%m-%d %H:%M:%S')}")

            # Get errored content
            errored_content = query.all()

            if not errored_content:
                print("No errored content found matching criteria")
                return

            print(f"Found {len(errored_content)} errored content items")

            if dry_run:
                print("\nDRY RUN - Would reset the following content:")
                for content in errored_content[:20]:  # Show first 20 in dry run
                    ctype = content.content_type
                    print(f"  - ID: {content.id}, Type: {ctype}, Source: {content.source}")
                    print(f"    URL: {content.url[:80]}...")
                    if content.error_message:
                        print(f"    Error: {content.error_message[:100]}...")
                if len(errored_content) > 20:
                    print(f"  ... and {len(errored_content) - 20} more")
                return

            # Delete existing processing tasks for errored content
            content_ids = [c.id for c in errored_content]
            deleted_tasks = (
                db.query(ProcessingTask)
                .filter(ProcessingTask.content_id.in_(content_ids))
                .delete(synchronize_session=False)
            )
            print(f"Deleted {deleted_tasks} existing processing tasks")

            # Reset content status and clear error data
            reset_count = 0
            new_tasks = []

            for content in errored_content:
                # Reset content fields
                content.status = ContentStatus.NEW.value
                content.error_message = None
                content.retry_count = 0
                content.checked_out_by = None
                content.checked_out_at = None
                content.processed_at = None
                # Keep content_metadata as it may contain useful partial data

                # Create new processing task
                task = ProcessingTask(
                    task_type="process_content",
                    content_id=content.id,
                    status="pending",
                    payload={
                        "content_type": content.content_type,
                        "url": content.url,
                        "source": content.source,
                        "reset_from_error": True,
                        "original_error": content.error_message[:500]
                        if content.error_message
                        else None,
                    },
                )
                new_tasks.append(task)
                reset_count += 1

            # Add all new tasks
            db.add_all(new_tasks)

            # Commit all changes
            db.commit()

            print(f"\nSuccessfully reset {reset_count} errored content items")
            print(f"Created {len(new_tasks)} new processing tasks")
            print("\nYou can now run 'python scripts/run_workers.py' to process the reset content")

            # Show summary by content type
            type_counts = {}
            for content in errored_content:
                type_counts[content.content_type] = type_counts.get(content.content_type, 0) + 1

            print("\nContent reset by type:")
            for content_type, count in sorted(type_counts.items()):
                print(f"  - {content_type}: {count}")

        except Exception as e:
            db.rollback()
            print(f"Error: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(
        description="Reset errored content for re-processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Reset all errored content
  python scripts/reset_errored_content.py

  # Reset only content errored in the last 7 days
  python scripts/reset_errored_content.py --days 7

  # Dry run to see what would be reset (last 3 days)
  python scripts/reset_errored_content.py --days 3 --dry-run

  # Reset content errored since a specific date
  python scripts/reset_errored_content.py --since 2024-12-01

  # Reset content errored in a specific date range
  python scripts/reset_errored_content.py --since "2024-12-01 08:00" --until "2024-12-01 12:00"

  # Combine --since with --until for precise ranges
  python scripts/reset_errored_content.py --since 2024-12-01T00:00:00 --until 2024-12-02T00:00:00
        """,
    )

    parser.add_argument(
        "--days",
        type=int,
        help="Only reset content errored within this many days (default: all errored content)",
    )

    parser.add_argument(
        "--since",
        type=parse_datetime,
        help="Only reset content errored on or after this datetime (YYYY-MM-DD)",
    )

    parser.add_argument(
        "--until",
        type=parse_datetime,
        help="Only reset content errored before this datetime (YYYY-MM-DD or YYYY-MM-DD HH:MM)",
    )

    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be reset without making changes"
    )

    args = parser.parse_args()

    # Validate conflicting options
    if args.days and (args.since or args.until):
        parser.error("Cannot use --days together with --since/--until")

    if args.dry_run:
        print("DRY RUN MODE - No changes will be made\n")

    reset_errored_content(days=args.days, since=args.since, until=args.until, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
