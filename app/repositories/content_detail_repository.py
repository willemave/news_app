"""Repository for detailed content queries."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.schema import Content, ContentDiscussion
from app.repositories.content_repository import build_visibility_context


def get_content_detail(db: Session, *, user_id: int, content_id: int):
    """Return detail row with read/favorite flags."""
    context = build_visibility_context(user_id)
    return (
        db.query(
            Content,
            context.is_read.label("is_read"),
            context.is_favorited.label("is_favorited"),
        )
        .filter(Content.id == content_id)
        .first()
    )


def get_content_discussion(db: Session, *, content_id: int):
    """Return content and discussion rows for discussion endpoint."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        return None, None
    discussion = (
        db.query(ContentDiscussion).filter(ContentDiscussion.content_id == content_id).first()
    )
    return content, discussion
