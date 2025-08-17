"""Repository for content favorites operations."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schema import ContentFavorites


def toggle_favorite(db: Session, content_id: int) -> tuple[bool, ContentFavorites | None]:
    """Toggle favorite status for content (single user app, no session needed).
    
    Returns:
        Tuple of (is_favorited, favorite_record)
    """
    print(f"[FAVORITES] Toggling favorite for content_id={content_id}")
    try:
        # Check if already favorited
        existing = db.execute(
            select(ContentFavorites).where(ContentFavorites.content_id == content_id)
        ).scalar_one_or_none()

        if existing:
            # Remove from favorites
            print("[FAVORITES] Content already favorited, removing from favorites")
            db.delete(existing)
            db.commit()
            return (False, None)

        # Add to favorites
        print("[FAVORITES] Adding content to favorites")
        favorite = ContentFavorites(
            session_id="default",  # Single user, use default session
            content_id=content_id,
            favorited_at=datetime.utcnow(),
        )
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
        print(f"[FAVORITES] Successfully added to favorites with id={favorite.id}")
        return (True, favorite)
    except IntegrityError as e:
        print(f"[FAVORITES] IntegrityError: {e}")
        db.rollback()
        return (False, None)
    except Exception as e:
        print(f"[FAVORITES] Unexpected error: {e}")
        db.rollback()
        return (False, None)


def add_favorite(db: Session, content_id: int) -> ContentFavorites | None:
    """Add content to favorites."""
    print(f"[FAVORITES] Adding content_id={content_id} to favorites")
    try:
        # Check if already favorited
        existing = db.execute(
            select(ContentFavorites).where(ContentFavorites.content_id == content_id)
        ).scalar_one_or_none()

        if existing:
            print("[FAVORITES] Content already in favorites")
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
        print(f"[FAVORITES] Successfully added to favorites with id={favorite.id}")
        return favorite
    except Exception as e:
        print(f"[FAVORITES] Error adding to favorites: {e}")
        db.rollback()
        return None


def remove_favorite(db: Session, content_id: int) -> bool:
    """Remove content from favorites."""
    print(f"[FAVORITES] Removing content_id={content_id} from favorites")
    try:
        result = db.execute(
            delete(ContentFavorites).where(ContentFavorites.content_id == content_id)
        )
        db.commit()
        deleted = result.rowcount > 0
        print(f"[FAVORITES] Removed from favorites: {deleted}")
        return deleted
    except Exception as e:
        print(f"[FAVORITES] Error removing from favorites: {e}")
        db.rollback()
        return False


def get_favorite_content_ids(db: Session) -> list[int]:
    """Get all content IDs that have been favorited."""
    print("[FAVORITES] Getting all favorited content IDs")
    result = db.execute(select(ContentFavorites.content_id).distinct()).scalars().all()
    content_ids = list(result)
    print(f"[FAVORITES] Found {len(content_ids)} favorited content IDs: {content_ids}")
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