"""Repository for content unlikes operations."""

import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schema import ContentUnlikes


logger = logging.getLogger(__name__)


def toggle_unlike(db: Session, content_id: int) -> tuple[bool, ContentUnlikes | None]:
    """Toggle unlike status for content (single user app, no session needed).
    
    Returns:
        Tuple of (is_unliked, unlike_record)
    """
    logger.debug("Toggling unlike for content_id=%s", content_id)
    try:
        # Check if already unliked
        existing = db.execute(
            select(ContentUnlikes).where(ContentUnlikes.content_id == content_id)
        ).scalar_one_or_none()

        if existing:
            # Remove from unlikes
            logger.debug("Content already unliked; removing content_id=%s", content_id)
            db.delete(existing)
            db.commit()
            return (False, None)

        # Add to unlikes
        logger.debug("Adding content_id=%s to unlikes", content_id)
        unlike = ContentUnlikes(
            session_id="default",  # Single user, use default session
            content_id=content_id,
            unliked_at=datetime.utcnow(),
        )
        db.add(unlike)
        db.commit()
        db.refresh(unlike)
        logger.debug("Successfully added content_id=%s to unlikes with id=%s", content_id, unlike.id)
        return (True, unlike)
    except IntegrityError:
        logger.exception("Integrity error toggling unlike for content_id=%s", content_id)
        db.rollback()
        return (False, None)
    except Exception:
        logger.exception("Unexpected error toggling unlike for content_id=%s", content_id)
        db.rollback()
        return (False, None)


def remove_unlike(db: Session, content_id: int) -> bool:
    """Remove content from unlikes."""
    logger.debug("Removing content_id=%s from unlikes", content_id)
    try:
        result = db.execute(
            delete(ContentUnlikes).where(ContentUnlikes.content_id == content_id)
        )
        db.commit()
        deleted = result.rowcount > 0
        logger.debug("Removed content_id=%s from unlikes=%s", content_id, deleted)
        return deleted
    except Exception:
        logger.exception("Error removing content_id=%s from unlikes", content_id)
        db.rollback()
        return False


def get_unliked_content_ids(db: Session) -> list[int]:
    """Get all content IDs that have been unliked."""
    logger.debug("Fetching all unliked content IDs")
    result = db.execute(select(ContentUnlikes.content_id).distinct()).scalars().all()
    content_ids = list(result)
    logger.debug("Found %s unliked content IDs", len(content_ids))
    return content_ids


def is_content_unliked(db: Session, content_id: int) -> bool:
    """Check if content has been unliked."""
    result = db.execute(
        select(ContentUnlikes).where(ContentUnlikes.content_id == content_id)
    ).scalar_one_or_none()
    return result is not None


def clear_unlikes(db: Session, session_id: str = "default") -> int:
    """Clear all unlikes for a session."""
    result = db.execute(delete(ContentUnlikes).where(ContentUnlikes.session_id == session_id))
    db.commit()
    return result.rowcount
