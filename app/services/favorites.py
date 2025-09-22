"""Repository for content favorites operations."""

import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schema import ContentFavorites


logger = logging.getLogger(__name__)


def toggle_favorite(db: Session, content_id: int) -> tuple[bool, ContentFavorites | None]:
    """Toggle favorite status for content (single user app, no session needed).
    
    Returns:
        Tuple of (is_favorited, favorite_record)
    """
    logger.debug("Toggling favorite for content_id=%s", content_id)
    try:
        # Check if already favorited
        existing = db.execute(
            select(ContentFavorites).where(ContentFavorites.content_id == content_id)
        ).scalar_one_or_none()

        if existing:
            # Remove from favorites
            logger.debug("Content already favorited; removing content_id=%s", content_id)
            db.delete(existing)
            db.commit()
            return (False, None)

        # Add to favorites
        logger.debug("Adding content_id=%s to favorites", content_id)
        favorite = ContentFavorites(
            session_id="default",  # Single user, use default session
            content_id=content_id,
            favorited_at=datetime.utcnow(),
        )
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
        logger.debug("Successfully added content_id=%s to favorites with id=%s", content_id, favorite.id)
        return (True, favorite)
    except IntegrityError:
        logger.exception("Integrity error toggling favorite for content_id=%s", content_id)
        db.rollback()
        return (False, None)
    except Exception:
        logger.exception("Unexpected error toggling favorite for content_id=%s", content_id)
        db.rollback()
        return (False, None)


def add_favorite(db: Session, content_id: int) -> ContentFavorites | None:
    """Add content to favorites."""
    logger.debug("Adding content_id=%s to favorites", content_id)
    try:
        # Check if already favorited
        existing = db.execute(
            select(ContentFavorites).where(ContentFavorites.content_id == content_id)
        ).scalar_one_or_none()

        if existing:
            logger.debug("Content already in favorites; content_id=%s", content_id)
            return existing

        # Add to favorites
        favorite = ContentFavorites(
            session_id="default",
            content_id=content_id,
            favorited_at=datetime.utcnow(),
        )
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
        logger.debug("Successfully added content_id=%s to favorites with id=%s", content_id, favorite.id)
        return favorite
    except Exception:
        logger.exception("Error adding content_id=%s to favorites", content_id)
        db.rollback()
        return None


def remove_favorite(db: Session, content_id: int) -> bool:
    """Remove content from favorites."""
    logger.debug("Removing content_id=%s from favorites", content_id)
    try:
        result = db.execute(
            delete(ContentFavorites).where(ContentFavorites.content_id == content_id)
        )
        db.commit()
        deleted = result.rowcount > 0
        logger.debug("Removed content_id=%s from favorites=%s", content_id, deleted)
        return deleted
    except Exception:
        logger.exception("Error removing content_id=%s from favorites", content_id)
        db.rollback()
        return False


def get_favorite_content_ids(db: Session) -> list[int]:
    """Get all content IDs that have been favorited."""
    logger.debug("Fetching all favorited content IDs")
    result = db.execute(select(ContentFavorites.content_id).distinct()).scalars().all()
    content_ids = list(result)
    logger.debug("Found %s favorited content IDs", len(content_ids))
    return content_ids


def is_content_favorited(db: Session, content_id: int) -> bool:
    """Check if content has been favorited."""
    result = db.execute(
        select(ContentFavorites).where(ContentFavorites.content_id == content_id)
    ).scalar_one_or_none()
    return result is not None


def clear_favorites(db: Session, session_id: str = "default") -> int:
    """Clear all favorites for a session."""
    result = db.execute(delete(ContentFavorites).where(ContentFavorites.session_id == session_id))
    db.commit()
    return result.rowcount
