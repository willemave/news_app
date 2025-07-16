"""Repository for content read status operations."""

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.schema import ContentReadStatus


def mark_content_as_read(db: Session, content_id: int) -> ContentReadStatus | None:
    """Mark content as read (single user app, no session needed)."""
    print(f"[READ_STATUS] Attempting to mark content_id={content_id} as read")
    try:
        # Check if already marked as read
        existing = db.execute(
            select(ContentReadStatus).where(ContentReadStatus.content_id == content_id)
        ).scalar_one_or_none()

        if existing:
            # Update read_at timestamp
            print("[READ_STATUS] Content already marked as read, updating timestamp")
            existing.read_at = datetime.utcnow()
            db.commit()
            return existing

        # Create new read status
        print("[READ_STATUS] Creating new read status record")
        read_status = ContentReadStatus(
            session_id="default",  # Single user, use default session
            content_id=content_id,
            read_at=datetime.utcnow(),
        )
        db.add(read_status)
        db.commit()
        db.refresh(read_status)
        print(f"[READ_STATUS] Successfully created read status with id={read_status.id}")
        return read_status
    except IntegrityError as e:
        print(f"[READ_STATUS] IntegrityError: {e}")
        db.rollback()
        return None
    except Exception as e:
        print(f"[READ_STATUS] Unexpected error: {e}")
        db.rollback()
        return None


def get_read_content_ids(db: Session) -> list[int]:
    """Get all content IDs that have been read."""
    print("[READ_STATUS] Getting all read content IDs")
    result = db.execute(select(ContentReadStatus.content_id).distinct()).scalars().all()
    content_ids = list(result)
    print(f"[READ_STATUS] Found {len(content_ids)} read content IDs: {content_ids}")
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
