"""Repository for content unlikes operations."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schema import ContentUnlikes


def toggle_unlike(db: Session, content_id: int) -> tuple[bool, ContentUnlikes | None]:
    """Toggle unlike status for content (single user app, no session needed).
    
    Returns:
        Tuple of (is_unliked, unlike_record)
    """
    print(f"[UNLIKES] Toggling unlike for content_id={content_id}")
    try:
        # Check if already unliked
        existing = db.execute(
            select(ContentUnlikes).where(ContentUnlikes.content_id == content_id)
        ).scalar_one_or_none()

        if existing:
            # Remove from unlikes
            print("[UNLIKES] Content already unliked, removing from unlikes")
            db.delete(existing)
            db.commit()
            return (False, None)

        # Add to unlikes
        print("[UNLIKES] Adding content to unlikes")
        unlike = ContentUnlikes(
            session_id="default",  # Single user, use default session
            content_id=content_id,
            unliked_at=datetime.utcnow(),
        )
        db.add(unlike)
        db.commit()
        db.refresh(unlike)
        print(f"[UNLIKES] Successfully added to unlikes with id={unlike.id}")
        return (True, unlike)
    except IntegrityError as e:
        print(f"[UNLIKES] IntegrityError: {e}")
        db.rollback()
        return (False, None)
    except Exception as e:
        print(f"[UNLIKES] Unexpected error: {e}")
        db.rollback()
        return (False, None)


def remove_unlike(db: Session, content_id: int) -> bool:
    """Remove content from unlikes."""
    print(f"[UNLIKES] Removing content_id={content_id} from unlikes")
    try:
        result = db.execute(
            delete(ContentUnlikes).where(ContentUnlikes.content_id == content_id)
        )
        db.commit()
        deleted = result.rowcount > 0
        print(f"[UNLIKES] Removed from unlikes: {deleted}")
        return deleted
    except Exception as e:
        print(f"[UNLIKES] Error removing from unlikes: {e}")
        db.rollback()
        return False


def get_unliked_content_ids(db: Session) -> list[int]:
    """Get all content IDs that have been unliked."""
    print("[UNLIKES] Getting all unliked content IDs")
    result = db.execute(select(ContentUnlikes.content_id).distinct()).scalars().all()
    content_ids = list(result)
    print(f"[UNLIKES] Found {len(content_ids)} unliked content IDs: {content_ids}")
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

