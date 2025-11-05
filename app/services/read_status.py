"""Repository for content read status operations."""

import logging
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schema import ContentReadStatus

logger = logging.getLogger(__name__)


def mark_content_as_read(db: Session, content_id: int, user_id: int) -> ContentReadStatus | None:
    """Mark content as read for a user.

    Args:
        db: Database session
        content_id: ID of content to mark as read
        user_id: ID of user performing action

    Returns:
        ContentReadStatus record or None on error
    """
    logger.info(
        "[READ_STATUS] Marking content_id=%s as read for user_id=%s",
        content_id,
        user_id,
        extra={"content_id": content_id, "user_id": user_id},
    )
    try:
        existing = db.execute(
            select(ContentReadStatus).where(
                ContentReadStatus.content_id == content_id, ContentReadStatus.user_id == user_id
            )
        ).scalar_one_or_none()

        if existing:
            logger.debug(
                "[READ_STATUS] Content already marked as read; refreshing timestamp",
                extra={"content_id": content_id, "user_id": user_id},
            )
            existing.read_at = datetime.utcnow()
            db.commit()
            return existing

        read_status = ContentReadStatus(
            user_id=user_id,
            content_id=content_id,
            read_at=datetime.utcnow(),
        )
        db.add(read_status)
        db.commit()
        db.refresh(read_status)
        logger.info(
            "[READ_STATUS] Created read status record with id=%s",
            read_status.id,
            extra={"content_id": content_id, "user_id": user_id, "read_status_id": read_status.id},
        )
        return read_status
    except IntegrityError as exc:
        logger.warning(
            "[READ_STATUS] Integrity error while marking read",
            extra={"content_id": content_id, "user_id": user_id, "error": str(exc)},
            exc_info=True,
        )
        db.rollback()
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[READ_STATUS] Unexpected error while marking read",
            extra={"content_id": content_id, "user_id": user_id, "error": str(exc)},
        )
        db.rollback()
        return None


def mark_contents_as_read(
    db: Session,
    content_ids: Iterable[int],
    user_id: int,
) -> tuple[int, list[int]]:
    """Mark a batch of content items as read for a user.

    Args:
        db: Active database session
        content_ids: Iterable of content IDs to mark as read
        user_id: ID of user performing action

    Returns:
        A tuple containing the number of processed IDs and a list of IDs that failed
    """

    unique_ids = {content_id for content_id in content_ids if content_id is not None}
    if not unique_ids:
        return 0, []

    logger.info(
        "[READ_STATUS] Bulk marking %s content items as read for user_id=%s",
        len(unique_ids),
        user_id,
        extra={"content_ids": sorted(unique_ids), "user_id": user_id},
    )

    timestamp = datetime.utcnow()
    try:
        existing_records = (
            db.execute(
                select(ContentReadStatus).where(
                    ContentReadStatus.content_id.in_(unique_ids),
                    ContentReadStatus.user_id == user_id,
                )
            )
            .scalars()
            .all()
        )

        existing_ids = {record.content_id for record in existing_records}
        for record in existing_records:
            record.read_at = timestamp

        new_ids = sorted(unique_ids - existing_ids)
        if new_ids:
            db.bulk_save_objects(
                [
                    ContentReadStatus(
                        user_id=user_id,
                        content_id=content_id,
                        read_at=timestamp,
                        created_at=timestamp,
                    )
                    for content_id in new_ids
                ]
            )

        db.commit()
        return len(unique_ids), []
    except IntegrityError as exc:
        logger.warning(
            "[READ_STATUS] Integrity error during bulk mark; retrying individually",
            extra={"user_id": user_id, "error": str(exc)},
            exc_info=True,
        )
        db.rollback()

        failed_ids: list[int] = []
        marked_count = 0
        for content_id in sorted(unique_ids):
            result = mark_content_as_read(db, content_id, user_id)
            if result is None:
                failed_ids.append(content_id)
                continue
            marked_count += 1

        return marked_count, failed_ids
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[READ_STATUS] Unexpected error during bulk mark",
            extra={"user_id": user_id, "error": str(exc)},
        )
        db.rollback()
        return 0, sorted(unique_ids)


def get_read_content_ids(db: Session, user_id: int) -> list[int]:
    """Get all content IDs that have been read by a user.

    Args:
        db: Database session
        user_id: ID of user

    Returns:
        List of content IDs read by user
    """
    logger.debug("[READ_STATUS] Fetching read content IDs for user_id=%s", user_id)
    result = (
        db.execute(
            select(ContentReadStatus.content_id)
            .where(ContentReadStatus.user_id == user_id)
            .distinct()
        )
        .scalars()
        .all()
    )
    content_ids = list(result)
    logger.info(
        "[READ_STATUS] Found %s read content IDs for user_id=%s",
        len(content_ids),
        user_id,
        extra={"read_count": len(content_ids), "user_id": user_id},
    )
    return content_ids


def is_content_read(db: Session, content_id: int, user_id: int) -> bool:
    """Check if content has been read by a user.

    Args:
        db: Database session
        content_id: ID of content
        user_id: ID of user

    Returns:
        True if read, False otherwise
    """
    result = db.execute(
        select(ContentReadStatus).where(
            ContentReadStatus.content_id == content_id, ContentReadStatus.user_id == user_id
        )
    ).scalar_one_or_none()
    return result is not None


def clear_read_status(db: Session, user_id: int) -> int:
    """Clear all read status for a user.

    Args:
        db: Database session
        user_id: ID of user

    Returns:
        Number of read status records cleared
    """
    result = db.execute(delete(ContentReadStatus).where(ContentReadStatus.user_id == user_id))
    db.commit()
    return result.rowcount
