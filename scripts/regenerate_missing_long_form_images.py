#!/usr/bin/env python3
"""Enqueue image regeneration for long-form items missing generated images.

Usage:
    python scripts/regenerate_missing_long_form_images.py
    python scripts/regenerate_missing_long_form_images.py --apply
    python scripts/regenerate_missing_long_form_images.py --apply --limit 50
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

from sqlalchemy import and_, exists, not_, select

# Add parent directory so we can import from app.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import get_db  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.models.contracts import TaskStatus  # noqa: E402
from app.models.metadata import ContentStatus, ContentType  # noqa: E402
from app.models.schema import Content, ContentStatusEntry, ProcessingTask  # noqa: E402
from app.services.queue import QueueService, TaskType  # noqa: E402
from app.utils.image_paths import get_content_images_dir  # noqa: E402

LONG_FORM_TYPES = [ContentType.ARTICLE.value, ContentType.PODCAST.value]
CONTENT_IMAGES_DIR = get_content_images_dir()


def _is_youtube_podcast_with_thumbnail(content: Content) -> bool:
    """Return True when a podcast already has a provider thumbnail.

    Args:
        content: Content row to inspect.

    Returns:
        Whether the podcast should rely on an existing external thumbnail.
    """
    if content.content_type != ContentType.PODCAST.value:
        return False

    metadata = content.content_metadata or {}
    return bool(metadata.get("thumbnail_url") or metadata.get("video_id"))


def _has_summary(content: Content) -> bool:
    """Return True when content has summary data suitable for image prompts.

    Args:
        content: Content row to inspect.

    Returns:
        Whether the content includes summary metadata.
    """
    metadata = content.content_metadata or {}
    return bool(metadata.get("summary"))


def _needs_image_regeneration(content: Content) -> tuple[bool, str]:
    """Determine whether content should have an image generation task enqueued.

    Args:
        content: Content row to inspect.

    Returns:
        Tuple of `(should_enqueue, reason)`.
    """
    if _is_youtube_podcast_with_thumbnail(content):
        return False, "external_thumbnail"

    if not _has_summary(content):
        return False, "missing_summary"

    metadata = content.content_metadata or {}
    image_path = CONTENT_IMAGES_DIR / f"{content.id}.png"
    has_image_file = image_path.exists()
    has_image_reference = bool(metadata.get("image_generated_at") or metadata.get("image_url"))

    if not has_image_file:
        return True, "missing_image_file"

    if not has_image_reference:
        return True, "missing_image_metadata"

    return False, "already_has_generated_image"


def enqueue_missing_long_form_images(
    *,
    apply: bool,
    limit: int | None,
) -> None:
    """Scan long-form inbox items and enqueue image regeneration as needed.

    Args:
        apply: When True, enqueue tasks. Otherwise print a dry-run report.
        limit: Maximum number of candidate content rows to scan.
    """
    CONTENT_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    in_inbox = exists(
        select(ContentStatusEntry.id).where(
            ContentStatusEntry.content_id == Content.id,
            ContentStatusEntry.status == "inbox",
        )
    )
    has_active_generate_image_task = exists(
        select(ProcessingTask.id).where(
            ProcessingTask.content_id == Content.id,
            ProcessingTask.task_type == TaskType.GENERATE_IMAGE.value,
            ProcessingTask.status.in_(
                [TaskStatus.PENDING.value, TaskStatus.PROCESSING.value]
            ),
        )
    )

    with get_db() as db:
        query = (
            db.query(Content)
            .filter(
                and_(
                    Content.status == ContentStatus.COMPLETED.value,
                    Content.content_type.in_(LONG_FORM_TYPES),
                    in_inbox,
                    not_(has_active_generate_image_task),
                )
            )
            .order_by(Content.created_at.desc())
        )
        if limit is not None:
            query = query.limit(limit)

        content_items = query.all()

        print("Scanning for missing long-form images")
        print(f"  apply={apply}")
        print(f"  limit={limit}")
        print(f"  scanned={len(content_items)}")

        reason_counts: Counter[str] = Counter()
        enqueue_ids: list[int] = []

        for content in content_items:
            should_enqueue, reason = _needs_image_regeneration(content)
            reason_counts[reason] += 1
            if not should_enqueue:
                continue
            enqueue_ids.append(content.id)
            if not apply:
                title = (content.title or "Untitled")[:80]
                print(
                    "  would_enqueue "
                    f"content_id={content.id} type={content.content_type} title={title}"
                )

        print()
        print("Summary:")
        print(f"  enqueue_candidates={len(enqueue_ids)}")
        for reason, count in sorted(reason_counts.items()):
            print(f"  {reason}={count}")

        if not apply:
            return

        queue_service = QueueService()
        enqueued = 0
        for content_id in enqueue_ids:
            queue_service.enqueue(
                task_type=TaskType.GENERATE_IMAGE,
                content_id=content_id,
            )
            enqueued += 1

        print(f"  enqueued={enqueued}")


def parse_args() -> argparse.Namespace:
    """Parse CLI args for the script."""
    parser = argparse.ArgumentParser(
        description="Regenerate missing generated images for long-form content"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Enqueue image generation tasks. Default is dry-run output only.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of completed long-form items to scan.",
    )
    return parser.parse_args()


def main() -> None:
    """Run the missing long-form image regeneration scan."""
    setup_logging()
    args = parse_args()
    enqueue_missing_long_form_images(
        apply=args.apply,
        limit=args.limit,
    )


if __name__ == "__main__":
    main()
