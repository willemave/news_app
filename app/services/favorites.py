"""Repository for content favorites operations."""

import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schema import ContentFavorites

logger = logging.getLogger(__name__)


def toggle_favorite(db: Session, content_id: int, user_id: int) -> tuple[bool, ContentFavorites | None]:
    """Toggle favorite status for content.

    Args:
        db: Database session
        content_id: ID of content to toggle
        user_id: ID of user performing action

    Returns:
        Tuple of (is_favorited, favorite_record)
    """
    logger.debug("Toggling favorite for content_id=%s, user_id=%s", content_id, user_id)
    try:
        # Check if already favorited
        existing = db.execute(
            select(ContentFavorites).where(
                ContentFavorites.content_id == content_id,
                ContentFavorites.user_id == user_id
            )
        ).scalar_one_or_none()

        if existing:
            # Remove from favorites
            logger.debug("Content already favorited; removing content_id=%s for user_id=%s", content_id, user_id)
            db.delete(existing)
            db.commit()
            return (False, None)

        # Add to favorites
        logger.debug("Adding content_id=%s to favorites for user_id=%s", content_id, user_id)
        favorite = ContentFavorites(
            user_id=user_id,
            content_id=content_id,
            favorited_at=datetime.utcnow(),
        )
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
        logger.debug("Successfully added content_id=%s to favorites with id=%s for user_id=%s", content_id, favorite.id, user_id)
        return (True, favorite)
    except IntegrityError:
        logger.exception("Integrity error toggling favorite for content_id=%s, user_id=%s", content_id, user_id)
        db.rollback()
        return (False, None)
    except Exception:
        logger.exception("Unexpected error toggling favorite for content_id=%s, user_id=%s", content_id, user_id)
        db.rollback()
        return (False, None)


def add_favorite(db: Session, content_id: int, user_id: int) -> ContentFavorites | None:
    """Add content to favorites.

    Args:
        db: Database session
        content_id: ID of content to favorite
        user_id: ID of user performing action

    Returns:
        ContentFavorites record or None on error
    """
    logger.debug("Adding content_id=%s to favorites for user_id=%s", content_id, user_id)
    try:
        # Check if already favorited
        existing = db.execute(
            select(ContentFavorites).where(
                ContentFavorites.content_id == content_id,
                ContentFavorites.user_id == user_id
            )
        ).scalar_one_or_none()

        if existing:
            logger.debug("Content already in favorites; content_id=%s, user_id=%s", content_id, user_id)
            return existing

        # Add to favorites
        favorite = ContentFavorites(
            user_id=user_id,
            content_id=content_id,
            favorited_at=datetime.utcnow(),
        )
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
        logger.debug("Successfully added content_id=%s to favorites with id=%s for user_id=%s", content_id, favorite.id, user_id)
        return favorite
    except Exception:
        logger.exception("Error adding content_id=%s to favorites for user_id=%s", content_id, user_id)
        db.rollback()
        return None


def remove_favorite(db: Session, content_id: int, user_id: int) -> bool:
    """Remove content from favorites.

    Args:
        db: Database session
        content_id: ID of content to unfavorite
        user_id: ID of user performing action

    Returns:
        True if removed, False otherwise
    """
    logger.debug("Removing content_id=%s from favorites for user_id=%s", content_id, user_id)
    try:
        result = db.execute(
            delete(ContentFavorites).where(
                ContentFavorites.content_id == content_id,
                ContentFavorites.user_id == user_id
            )
        )
        db.commit()
        deleted = result.rowcount > 0
        logger.debug("Removed content_id=%s from favorites for user_id=%s: %s", content_id, user_id, deleted)
        return deleted
    except Exception:
        logger.exception("Error removing content_id=%s from favorites for user_id=%s", content_id, user_id)
        db.rollback()
        return False


def get_favorite_content_ids(db: Session, user_id: int) -> list[int]:
    """Get all content IDs that have been favorited by a user.

    Args:
        db: Database session
        user_id: ID of user

    Returns:
        List of content IDs favorited by user
    """
    logger.debug("Fetching favorited content IDs for user_id=%s", user_id)
    result = db.execute(
        select(ContentFavorites.content_id)
        .where(ContentFavorites.user_id == user_id)
        .distinct()
    ).scalars().all()
    content_ids = list(result)
    logger.debug("Found %s favorited content IDs for user_id=%s", len(content_ids), user_id)
    return content_ids


def is_content_favorited(db: Session, content_id: int, user_id: int) -> bool:
    """Check if content has been favorited by a user.

    Args:
        db: Database session
        content_id: ID of content
        user_id: ID of user

    Returns:
        True if favorited, False otherwise
    """
    result = db.execute(
        select(ContentFavorites).where(
            ContentFavorites.content_id == content_id,
            ContentFavorites.user_id == user_id
        )
    ).scalar_one_or_none()
    return result is not None


def clear_favorites(db: Session, user_id: int) -> int:
    """Clear all favorites for a user.

    Args:
        db: Database session
        user_id: ID of user

    Returns:
        Number of favorites cleared
    """
    result = db.execute(delete(ContentFavorites).where(ContentFavorites.user_id == user_id))
    db.commit()
    return result.rowcount
