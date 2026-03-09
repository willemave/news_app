"""Repository for content favorites operations."""

from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.schema import ChatMessage, ChatSession, Content, ContentFavorites
from app.services.llm_models import DEFAULT_MODEL, DEFAULT_PROVIDER

logger = get_logger(__name__)

DEFAULT_LLM_PROVIDER = DEFAULT_PROVIDER
DEFAULT_LLM_MODEL = DEFAULT_MODEL


def toggle_favorite(
    db: Session, content_id: int, user_id: int
) -> tuple[bool, ContentFavorites | None]:
    """Toggle favorite status for content."""
    logger.debug("Toggling favorite for content_id=%s, user_id=%s", content_id, user_id)
    try:
        existing = db.execute(
            select(ContentFavorites).where(
                ContentFavorites.content_id == content_id,
                ContentFavorites.user_id == user_id,
            )
        ).scalar_one_or_none()

        if existing:
            db.delete(existing)
            _delete_empty_chat_session(db, content_id, user_id)
            db.commit()
            return (False, None)

        favorite = ContentFavorites(
            user_id=user_id,
            content_id=content_id,
            favorited_at=datetime.now(UTC),
        )
        db.add(favorite)
        _create_chat_session_for_favorite(db, content_id, user_id)
        db.commit()
        db.refresh(favorite)
        return (True, favorite)
    except IntegrityError:
        logger.exception(
            "Integrity error toggling favorite for content_id=%s, user_id=%s",
            content_id,
            user_id,
        )
        db.rollback()
        return (False, None)
    except Exception:
        logger.exception(
            "Unexpected error toggling favorite for content_id=%s, user_id=%s",
            content_id,
            user_id,
        )
        db.rollback()
        return (False, None)


def _create_chat_session_for_favorite(db: Session, content_id: int, user_id: int) -> None:
    existing_session = db.execute(
        select(ChatSession).where(
            ChatSession.content_id == content_id,
            ChatSession.user_id == user_id,
            ChatSession.is_archived == False,  # noqa: E712
        )
    ).scalar_one_or_none()
    if existing_session:
        return

    content = db.execute(select(Content).where(Content.id == content_id)).scalar_one_or_none()
    title = content.title or content.source or "Saved Article" if content else "Saved Article"
    session = ChatSession(
        user_id=user_id,
        content_id=content_id,
        title=title,
        session_type="article_brain",
        llm_provider=DEFAULT_LLM_PROVIDER,
        llm_model=DEFAULT_LLM_MODEL,
        created_at=datetime.now(UTC),
    )
    db.add(session)


def _delete_empty_chat_session(db: Session, content_id: int, user_id: int) -> None:
    session = db.execute(
        select(ChatSession).where(
            ChatSession.content_id == content_id,
            ChatSession.user_id == user_id,
            ChatSession.is_archived == False,  # noqa: E712
        )
    ).scalar_one_or_none()
    if not session:
        return

    has_messages = db.execute(
        select(ChatMessage.id).where(ChatMessage.session_id == session.id).limit(1)
    ).scalar_one_or_none()
    if has_messages:
        return

    db.delete(session)


def add_favorite(db: Session, content_id: int, user_id: int) -> ContentFavorites | None:
    """Add content to favorites."""
    try:
        existing = db.execute(
            select(ContentFavorites).where(
                ContentFavorites.content_id == content_id,
                ContentFavorites.user_id == user_id,
            )
        ).scalar_one_or_none()
        if existing:
            return existing

        favorite = ContentFavorites(
            user_id=user_id,
            content_id=content_id,
            favorited_at=datetime.now(UTC),
        )
        db.add(favorite)
        db.commit()
        db.refresh(favorite)
        return favorite
    except Exception:
        logger.exception(
            "Error adding content_id=%s to favorites for user_id=%s",
            content_id,
            user_id,
        )
        db.rollback()
        return None


def remove_favorite(db: Session, content_id: int, user_id: int) -> bool:
    """Remove content from favorites."""
    try:
        result = db.execute(
            delete(ContentFavorites).where(
                ContentFavorites.content_id == content_id,
                ContentFavorites.user_id == user_id,
            )
        )
        db.commit()
        return result.rowcount > 0
    except Exception:
        logger.exception(
            "Error removing content_id=%s from favorites for user_id=%s",
            content_id,
            user_id,
        )
        db.rollback()
        return False


def get_favorite_content_ids(db: Session, user_id: int) -> list[int]:
    """Return favorited content ids for a user."""
    return list(
        db.execute(
            select(ContentFavorites.content_id)
            .where(ContentFavorites.user_id == user_id)
            .distinct()
        )
        .scalars()
        .all()
    )


def is_content_favorited(db: Session, content_id: int, user_id: int) -> bool:
    """Return whether a content item is favorited by the user."""
    return (
        db.execute(
            select(ContentFavorites).where(
                ContentFavorites.content_id == content_id,
                ContentFavorites.user_id == user_id,
            )
        ).scalar_one_or_none()
        is not None
    )


def clear_favorites(db: Session, user_id: int) -> int:
    """Clear all favorites for a user."""
    result = db.execute(delete(ContentFavorites).where(ContentFavorites.user_id == user_id))
    db.commit()
    return int(result.rowcount or 0)
