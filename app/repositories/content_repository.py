"""Repository helpers for content visibility and flags."""

import re
from dataclasses import dataclass

from sqlalchemy import and_, column, exists, or_, select, table, text
from sqlalchemy.orm import Session

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentFavorites, ContentReadStatus, ContentStatusEntry


@dataclass(frozen=True)
class VisibilityContext:
    """Prebuilt correlated subqueries for content visibility."""

    is_in_inbox: object
    is_read: object
    is_favorited: object


def build_visibility_context(user_id: int) -> VisibilityContext:
    """Create correlated subqueries for visibility and per-user flags."""
    is_in_inbox = exists(
        select(ContentStatusEntry.id).where(
            ContentStatusEntry.user_id == user_id,
            ContentStatusEntry.status == "inbox",
            ContentStatusEntry.content_id == Content.id,
        )
    )
    is_read = exists(
        select(ContentReadStatus.id).where(
            ContentReadStatus.user_id == user_id,
            ContentReadStatus.content_id == Content.id,
        )
    )
    is_favorited = exists(
        select(ContentFavorites.id).where(
            ContentFavorites.user_id == user_id,
            ContentFavorites.content_id == Content.id,
        )
    )
    return VisibilityContext(
        is_in_inbox=is_in_inbox,
        is_read=is_read,
        is_favorited=is_favorited,
    )


def apply_visibility_filters(query, context: VisibilityContext):
    """Apply visibility filters for list/search queries."""
    return query.filter(
        and_(
            Content.status == ContentStatus.COMPLETED.value,
            or_(
                Content.content_type == ContentType.NEWS.value,
                context.is_in_inbox,
            ),
        )
    ).filter((Content.classification != "skip") | (Content.classification.is_(None)))


def apply_read_filter(query, read_filter: str, context: VisibilityContext):
    """Apply read/unread filters using correlated subqueries."""
    if read_filter == "unread":
        return query.filter(~context.is_read)
    if read_filter == "read":
        return query.filter(context.is_read)
    return query


def get_visible_content_query(db: Session, context: VisibilityContext, include_flags: bool = False):
    """Return a base query for visible content."""
    if include_flags:
        query = db.query(
            Content,
            context.is_read.label("is_read"),
            context.is_favorited.label("is_favorited"),
        )
    else:
        query = db.query(Content)
    return apply_visibility_filters(query, context)


def build_fts_match_query(raw_query: str) -> str | None:
    """Build a safe FTS match query from raw user input."""
    tokens = re.findall(r"[A-Za-z0-9_]+", raw_query.lower())
    if not tokens:
        return None
    return " ".join(f"{token}*" for token in tokens)


def sqlite_fts_available(db: Session) -> bool:
    """Return True when SQLite FTS is available in this database."""
    bind = db.get_bind()
    if bind.dialect.name != "sqlite":
        return False
    result = db.execute(
        text("SELECT 1 FROM sqlite_master WHERE type='table' AND name='content_fts'")
    ).first()
    return result is not None


def apply_sqlite_fts_filter(query, match_query: str):
    """Join against FTS table and apply MATCH clause."""
    fts_table = table("content_fts", column("rowid"))
    return (
        query.join(fts_table, fts_table.c.rowid == Content.id)
        .filter(text("content_fts MATCH :match_query"))
        .params(match_query=match_query)
    )
