#!/usr/bin/env python3
"""Enqueue unread long-form content to be re-summarized with the narrative template."""

import argparse
import os
import sys
from datetime import UTC, datetime

from sqlalchemy import and_

# Add parent directory so we can import from app
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import get_db  # noqa: E402
from app.core.logging import get_logger, setup_logging  # noqa: E402
from app.models.metadata import ContentStatus  # noqa: E402
from app.models.schema import (  # noqa: E402
    Content,
    ContentReadStatus,
    ContentStatusEntry,
    ProcessingTask,
)
from app.services.queue import QueueService, TaskType  # noqa: E402

setup_logging()
logger = get_logger(__name__)

LONG_FORM_TYPES = ("article", "podcast")
INBOX_STATUS = "inbox"
ACTIVE_TASK_STATUSES = ("pending", "processing")


def _has_text_for_resummarization(content: Content) -> bool:
    """Return True when content has source text needed for summarization."""
    metadata = content.content_metadata or {}

    if content.content_type == "article":
        return bool(metadata.get("content") or metadata.get("content_to_summarize"))
    if content.content_type == "podcast":
        return bool(metadata.get("transcript") or metadata.get("content_to_summarize"))
    return False


def enqueue_unread_longform_resummarization(
    dry_run: bool = False,
    limit: int | None = None,
    user_ids: list[int] | None = None,
) -> None:
    """Enqueue summarize tasks for unread long-form inbox content.

    Args:
        dry_run: If True, print candidate rows without creating tasks.
        limit: Optional maximum number of candidate content rows to inspect.
        user_ids: Optional user ID filter; when omitted uses all users.
    """
    print("Starting unread long-form re-summarization enqueue")
    print(f"  dry_run={dry_run}")
    print(f"  limit={limit}")
    print(f"  user_ids={user_ids or 'all'}")
    print("  template=editorial_narrative_v1")
    print()

    queue_service = QueueService()

    with get_db() as db:
        unread_id_query = (
            db.query(Content.id)
            .join(
                ContentStatusEntry,
                and_(
                    ContentStatusEntry.content_id == Content.id,
                    ContentStatusEntry.status == INBOX_STATUS,
                ),
            )
            .outerjoin(
                ContentReadStatus,
                and_(
                    ContentReadStatus.content_id == Content.id,
                    ContentReadStatus.user_id == ContentStatusEntry.user_id,
                ),
            )
            .filter(
                Content.status == ContentStatus.COMPLETED.value,
                Content.content_type.in_(LONG_FORM_TYPES),
                (Content.classification != "skip") | (Content.classification.is_(None)),
                ContentReadStatus.id.is_(None),
            )
            .distinct()
            .order_by(Content.created_at.asc())
        )

        if user_ids:
            unread_id_query = unread_id_query.filter(ContentStatusEntry.user_id.in_(user_ids))

        if limit:
            unread_id_query = unread_id_query.limit(limit)

        unread_ids = [row[0] for row in unread_id_query.all()]
        if unread_ids:
            candidate_content = (
                db.query(Content)
                .filter(Content.id.in_(unread_ids))
                .order_by(Content.created_at.asc())
                .all()
            )
        else:
            candidate_content = []

        active_task_rows = (
            db.query(ProcessingTask.content_id)
            .filter(
                ProcessingTask.task_type == TaskType.SUMMARIZE.value,
                ProcessingTask.status.in_(ACTIVE_TASK_STATUSES),
                ProcessingTask.content_id.is_not(None),
            )
            .all()
        )
        active_task_content_ids = {row[0] for row in active_task_rows if row[0] is not None}

        print(f"Found {len(candidate_content)} unread long-form items in inbox")
        print(f"Found {len(active_task_content_ids)} content IDs with active summarize tasks")

        enqueued = 0
        skipped_no_text = 0
        skipped_active_task = 0

        for content in candidate_content:
            if content.id in active_task_content_ids:
                skipped_active_task += 1
                continue

            if not _has_text_for_resummarization(content):
                skipped_no_text += 1
                continue

            title = (content.title or "No title").strip()
            title_preview = title[:80]

            if dry_run:
                print(f"  Would enqueue [{content.content_type}] {content.id}: {title_preview}")
                continue

            task_id = queue_service.enqueue(
                task_type=TaskType.SUMMARIZE,
                content_id=content.id,
                payload={
                    "force_resummarize": True,
                    "template": "editorial_narrative_v1",
                    "source": "enqueue_unread_longform_resummarization",
                    "enqueued_at": datetime.now(UTC).isoformat(),
                },
            )
            logger.info(
                "Enqueued summarize task %s for content %s (%s)",
                task_id,
                content.id,
                content.content_type,
            )
            enqueued += 1

        print("\nSummary:")
        print(f"  Candidate unread long-form items: {len(candidate_content)}")
        if dry_run:
            print("  Would enqueue: (see list above)")
        else:
            print(f"  Enqueued summarize tasks: {enqueued}")
        print(f"  Skipped (missing source text): {skipped_no_text}")
        print(f"  Skipped (already has active summarize task): {skipped_active_task}")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the resummarization enqueue script.

    Returns:
        Parsed CLI namespace.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Enqueue unread long-form content (article/podcast) for "
            "re-summarization with editorial_narrative."
        )
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be enqueued without writing tasks",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of content items to enqueue",
    )
    parser.add_argument(
        "--users",
        nargs="+",
        type=int,
        metavar="USER_ID",
        help="Only include unread content for these user IDs (default: all users)",
    )
    return parser.parse_args()


def main() -> None:
    """Run the unread long-form re-summarization enqueue script."""
    args = parse_args()
    enqueue_unread_longform_resummarization(
        dry_run=args.dry_run,
        limit=args.limit,
        user_ids=args.users,
    )


if __name__ == "__main__":
    main()
