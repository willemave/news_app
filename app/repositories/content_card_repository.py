"""Projection-oriented repository for content card queries."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.metadata import ContentType
from app.models.schema import Content, ContentReadStatus
from app.repositories.content_feed_query import (
    apply_sort_timestamp_cursor,
    build_user_feed_query,
    content_sort_timestamp_expr,
)

AVAILABLE_DATES_LOOKBACK_DAYS = 120


def list_contents(
    db: Session,
    *,
    user_id: int,
    content_types: list[str] | None,
    date: str | None,
    read_filter: str,
    last_id: int | None,
    last_sort_timestamp: datetime | None,
    limit: int,
    include_available_dates: bool = True,
):
    """Return visible inbox card rows and available dates."""
    available_dates: list[str] = []
    sort_expr = content_sort_timestamp_expr()
    if include_available_dates and last_id is None and last_sort_timestamp is None:
        lookback_start = datetime.now(UTC) - timedelta(days=AVAILABLE_DATES_LOOKBACK_DAYS)
        available_dates_query = build_user_feed_query(db, user_id, mode="inbox").with_entities(
            func.date(sort_expr).label("date")
        )
        available_dates_query = available_dates_query.filter(sort_expr >= lookback_start)
        available_dates_query = (
            available_dates_query.distinct().order_by(func.date(sort_expr).desc()).limit(90)
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
        query = query.filter(sort_expr >= start_dt, sort_expr < end_dt)

    if read_filter == "unread":
        query = query.filter(ContentReadStatus.id.is_(None))
    elif read_filter == "read":
        query = query.filter(ContentReadStatus.id.is_not(None))

    query = apply_sort_timestamp_cursor(query, last_sort_timestamp, last_id, sort_expr=sort_expr)
    rows = query.order_by(sort_expr.desc(), Content.id.desc()).limit(limit + 1).all()
    return rows, available_dates


def get_knowledge_library_entries(
    db: Session,
    *,
    user_id: int,
    last_id: int | None,
    last_sort_timestamp: datetime | None,
    limit: int,
):
    """Return knowledge-library card rows."""
    query = build_user_feed_query(db, user_id, mode="knowledge_library")
    query = apply_sort_timestamp_cursor(query, last_sort_timestamp, last_id)
    return query.order_by(Content.created_at.desc(), Content.id.desc()).limit(limit + 1).all()


def get_recently_read(
    db: Session,
    *,
    user_id: int,
    last_id: int | None,
    last_read_at: datetime | None,
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
        query.order_by(ContentReadStatus.read_at.desc(), Content.id.desc()).limit(limit + 1).all()
    )


def list_content_types() -> list[str]:
    """Return public content type filters for card endpoints."""
    return [content_type.value for content_type in ContentType]
