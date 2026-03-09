"""Projection-oriented repository for content card queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.metadata import ContentType
from app.models.schema import Content, ContentReadStatus
from app.repositories.content_feed_query import apply_created_at_cursor, build_user_feed_query

AVAILABLE_DATES_LOOKBACK_DAYS = 120


def list_contents(
    db: Session,
    *,
    user_id: int,
    content_types: list[str] | None,
    date: str | None,
    read_filter: str,
    last_id: int | None,
    last_created_at,
    limit: int,
):
    """Return visible inbox card rows and available dates."""
    available_dates: list[str] = []
    if last_id is None and last_created_at is None:
        lookback_start = datetime.now(UTC) - timedelta(days=AVAILABLE_DATES_LOOKBACK_DAYS)
        available_dates_query = build_user_feed_query(db, user_id, mode="inbox").with_entities(
            func.date(Content.created_at).label("date")
        )
        available_dates_query = available_dates_query.filter(Content.created_at >= lookback_start)
        available_dates_query = (
            available_dates_query.distinct()
            .order_by(func.date(Content.created_at).desc())
            .limit(90)
        )
        for row in available_dates_query.all():
            if not row.date:
                continue
            available_dates.append(
                row.date if isinstance(row.date, str) else row.date.strftime("%Y-%m-%d")
            )

    query = build_user_feed_query(db, user_id, mode="inbox")
    if content_types:
        filtered_types = [content_type for content_type in content_types if content_type != "all"]
        if filtered_types:
            query = query.filter(Content.content_type.in_(filtered_types))

    if date:
        filter_date = datetime.strptime(date, "%Y-%m-%d").date()  # noqa: DTZ007
        start_dt = datetime.combine(filter_date, datetime.min.time())  # noqa: DTZ001
        end_dt = start_dt + timedelta(days=1)
        query = query.filter(Content.created_at >= start_dt, Content.created_at < end_dt)

    if read_filter == "unread":
        query = query.filter(ContentReadStatus.id.is_(None))
    elif read_filter == "read":
        query = query.filter(ContentReadStatus.id.is_not(None))

    query = apply_created_at_cursor(query, last_created_at, last_id)
    rows = query.order_by(Content.created_at.desc(), Content.id.desc()).limit(limit + 1).all()
    return rows, available_dates


def search_contents(
    db: Session,
    *,
    user_id: int,
    query_text: str,
    content_type: str,
    search_backend,
    cursor: tuple[int | None, object | None],
    limit: int,
    offset: int,
):
    """Return card rows for content search."""
    query = build_user_feed_query(db, user_id, mode="inbox")
    if content_type and content_type != "all":
        query = query.filter(Content.content_type == content_type)

    query = search_backend.apply_search(query, query_text)
    query = query.order_by(Content.created_at.desc(), Content.id.desc())

    last_id, last_created_at = cursor
    if last_id and last_created_at:
        query = apply_created_at_cursor(query, last_created_at, last_id)
    elif offset > 0:
        query = query.offset(offset)

    return query.limit(limit + 1).all()


def get_favorites(
    db: Session,
    *,
    user_id: int,
    last_id: int | None,
    last_created_at,
    limit: int,
):
    """Return favorited card rows."""
    query = build_user_feed_query(db, user_id, mode="favorites")
    query = apply_created_at_cursor(query, last_created_at, last_id)
    return query.order_by(Content.created_at.desc(), Content.id.desc()).limit(limit + 1).all()


def get_recently_read(
    db: Session,
    *,
    user_id: int,
    last_id: int | None,
    last_read_at,
    limit: int,
):
    """Return recently-read card rows ordered by read timestamp."""
    query = build_user_feed_query(db, user_id, mode="recently_read").add_columns(
        ContentReadStatus.read_at.label("read_at")
    )
    if last_id and last_read_at:
        query = query.filter(
            or_(
                ContentReadStatus.read_at < last_read_at,
                (ContentReadStatus.read_at == last_read_at) & (Content.id < last_id),
            )
        )
    return (
        query.order_by(ContentReadStatus.read_at.desc(), Content.id.desc())
        .limit(limit + 1)
        .all()
    )


def list_content_types() -> list[str]:
    """Return public content type filters for card endpoints."""
    return [content_type.value for content_type in ContentType]
