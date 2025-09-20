"""Repository for content read status operations."""

import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schema import ContentReadStatus

logger = logging.getLogger(__name__)


def mark_content_as_read(db: Session, content_id: int) -> ContentReadStatus | None:
    """Mark content as read (single user app, no session needed)."""
    logger.info(
        "[READ_STATUS] Marking content_id=%s as read",
        content_id,
        extra={"content_id": content_id},
    )
    try:
        existing = db.execute(
            select(ContentReadStatus).where(ContentReadStatus.content_id == content_id)
        ).scalar_one_or_none()

        if existing:
            logger.debug(
                "[READ_STATUS] Content already marked as read; refreshing timestamp",
                extra={"content_id": content_id},
            )
            existing.read_at = datetime.utcnow()
            db.commit()
            return existing

        read_status = ContentReadStatus(
            session_id="default",
            content_id=content_id,
            read_at=datetime.utcnow(),
        )
        db.add(read_status)
        db.commit()
        db.refresh(read_status)
        logger.info(
            "[READ_STATUS] Created read status record with id=%s",
            read_status.id,
            extra={"content_id": content_id, "read_status_id": read_status.id},
        )
        return read_status
    except IntegrityError as exc:
        logger.warning(
            "[READ_STATUS] Integrity error while marking read",
            extra={"content_id": content_id, "error": str(exc)},
            exc_info=True,
        )
        db.rollback()
        return None
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[READ_STATUS] Unexpected error while marking read",
            extra={"content_id": content_id, "error": str(exc)},
        )
        db.rollback()
        return None


def get_read_content_ids(db: Session) -> list[int]:
    """Get all content IDs that have been read."""
    logger.debug("[READ_STATUS] Fetching read content IDs")
    result = db.execute(select(ContentReadStatus.content_id).distinct()).scalars().all()
    content_ids = list(result)
    logger.info(
        "[READ_STATUS] Found %s read content IDs",
        len(content_ids),
        extra={"read_count": len(content_ids)},
    )
    return content_ids


def is_content_read(db: Session, content_id: int) -> bool:
    """Check if content has been read."""
    result = db.execute(
        select(ContentReadStatus).where(ContentReadStatus.content_id == content_id)
    ).scalar_one_or_none()
    return result is not None


def clear_read_status(db: Session, session_id: str) -> int:
    """Clear all read status for a session."""
    result = db.execute(delete(ContentReadStatus).where(ContentReadStatus.session_id == session_id))
    db.commit()
    return result.rowcount
