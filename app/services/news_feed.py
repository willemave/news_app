"""Visible news-item feed queries, presenters, and read-state helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.contracts import (
    ContentClassification,
    ContentStatus,
    ContentType,
    NewsItemStatus,
    NewsItemVisibilityScope,
)
from app.models.pagination import PaginationMetadata
from app.models.schema import NewsItem, NewsItemReadStatus
from app.routers.api.models import (
    ContentDetailResponse,
    ContentListResponse,
    ContentSummaryResponse,
)
from app.utils.pagination import PaginationCursor
from app.utils.url_utils import normalize_http_url


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def _resolve_item_url(item: NewsItem) -> str:
    for candidate in (
        item.article_url,
        item.canonical_story_url,
        item.discussion_url,
        item.canonical_item_url,
    ):
        normalized = normalize_http_url(candidate) if candidate else None
        if normalized:
            return normalized
    return f"https://newsly.invalid/news-items/{item.id}"


def _cluster_metadata(item: NewsItem) -> dict[str, Any]:
    raw_metadata = dict(item.raw_metadata or {})
    cluster = raw_metadata.get("cluster")
    return cluster if isinstance(cluster, dict) else {}


def _top_comment(item: NewsItem) -> dict[str, str] | None:
    raw_top_comment = dict(item.raw_metadata or {}).get("top_comment")
    if not isinstance(raw_top_comment, dict):
        return None
    author = str(raw_top_comment.get("author") or "unknown").strip() or "unknown"
    text = str(raw_top_comment.get("text") or "").strip()
    if not text:
        return None
    return {"author": author, "text": text}


def _content_status(item: NewsItem) -> ContentStatus:
    if item.status == "failed":
        return ContentStatus.FAILED
    if item.status == "processing":
        return ContentStatus.PROCESSING
    if item.status == "new":
        return ContentStatus.NEW
    return ContentStatus.COMPLETED


def _content_classification(item: NewsItem) -> ContentClassification | None:
    raw_summary = dict(item.raw_metadata or {}).get("summary")
    if not isinstance(raw_summary, dict):
        return None
    classification = raw_summary.get("classification")
    if classification in {ContentClassification.TO_READ.value, ContentClassification.SKIP.value}:
        return ContentClassification(classification)
    return None


def _present_summary(item: NewsItem, *, is_read: bool) -> ContentSummaryResponse:
    cluster = _cluster_metadata(item)
    discussion_snippets = cluster.get("discussion_snippets")
    top_comment = _top_comment(item)
    if top_comment is None and isinstance(discussion_snippets, list) and discussion_snippets:
        top_comment = {"author": "Related", "text": str(discussion_snippets[0]).strip()}

    return ContentSummaryResponse(
        id=item.id,
        content_type=ContentType.NEWS,
        url=_resolve_item_url(item),
        source_url=item.canonical_item_url or item.discussion_url,
        discussion_url=item.discussion_url,
        title=item.summary_title or item.article_title,
        source=item.source_label,
        platform=item.platform,
        status=_content_status(item),
        short_summary=item.summary_text,
        created_at=(item.ingested_at or item.created_at).isoformat(),
        processed_at=item.processed_at.isoformat() if item.processed_at else None,
        classification=_content_classification(item),
        publication_date=item.published_at.isoformat() if item.published_at else None,
        is_read=is_read,
        is_favorited=False,
        news_article_url=item.article_url or item.canonical_story_url,
        news_discussion_url=item.discussion_url or item.canonical_item_url,
        news_key_points=list(item.summary_key_points or []) or None,
        news_summary=item.summary_text,
        user_status=None,
        image_url=None,
        thumbnail_url=None,
        primary_topic=None,
        top_comment=top_comment,
        comment_count=item.cluster_size - 1 if item.cluster_size > 1 else None,
    )


def _present_detail(item: NewsItem, *, is_read: bool) -> ContentDetailResponse:
    metadata = dict(item.raw_metadata or {})
    article = metadata.get("article")
    if not isinstance(article, dict):
        article = {}
    article.setdefault("url", item.article_url or item.canonical_story_url)
    article.setdefault("title", item.article_title or item.summary_title)
    article.setdefault("source_domain", item.article_domain)
    metadata["article"] = article

    summary = metadata.get("summary")
    if not isinstance(summary, dict):
        summary = {}
    summary.setdefault("title", item.summary_title or item.article_title)
    summary.setdefault("article_url", item.article_url or item.canonical_story_url)
    summary.setdefault("key_points", list(item.summary_key_points or []))
    summary.setdefault("summary", item.summary_text)
    metadata["summary"] = summary

    metadata.setdefault("discussion_url", item.discussion_url)
    metadata.setdefault("cluster", _cluster_metadata(item))

    return ContentDetailResponse(
        id=item.id,
        content_type=ContentType.NEWS,
        url=_resolve_item_url(item),
        source_url=item.canonical_item_url or item.discussion_url,
        discussion_url=item.discussion_url,
        title=item.article_title,
        display_title=item.summary_title or item.article_title or f"News item {item.id}",
        source=item.source_label,
        status=_content_status(item),
        error_message=None,
        retry_count=0,
        metadata=metadata,
        created_at=(item.ingested_at or item.created_at).isoformat(),
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
        processed_at=item.processed_at.isoformat() if item.processed_at else None,
        checked_out_by=None,
        checked_out_at=None,
        publication_date=item.published_at.isoformat() if item.published_at else None,
        is_read=is_read,
        is_favorited=False,
        summary=item.summary_text,
        short_summary=item.summary_text,
        summary_kind=None,
        summary_version=None,
        structured_summary=None,
        bullet_points=[],
        quotes=[],
        topics=[],
        full_markdown=None,
        news_article_url=item.article_url or item.canonical_story_url,
        news_discussion_url=item.discussion_url or item.canonical_item_url,
        news_key_points=list(item.summary_key_points or []) or None,
        news_summary=item.summary_text,
        image_url=None,
        thumbnail_url=None,
        detected_feed=None,
        can_subscribe=False,
    )


def _visible_news_item_filter(user_id: int):
    return or_(
        NewsItem.visibility_scope == NewsItemVisibilityScope.GLOBAL.value,
        and_(
            NewsItem.visibility_scope == NewsItemVisibilityScope.USER.value,
            NewsItem.owner_user_id == user_id,
        ),
    )


def _news_item_is_read_clause(*, user_id: int):
    return exists(
        select(NewsItemReadStatus.id).where(
            NewsItemReadStatus.user_id == user_id,
            NewsItemReadStatus.news_item_id == NewsItem.id,
        )
    )


def _visible_news_item_query(db: Session, *, user_id: int):
    return (
        db.query(NewsItem)
        .filter(NewsItem.status == NewsItemStatus.READY.value)
        .filter(NewsItem.representative_news_item_id.is_(None))
        .filter(_visible_news_item_filter(user_id))
    )


def list_visible_news_items(
    db: Session,
    *,
    user_id: int,
    read_filter: str,
    cursor: str | None,
    limit: int,
) -> ContentListResponse:
    """Return the visible representative news feed for one user."""
    last_id = None
    last_ingested_at = None
    if cursor:
        cursor_data = PaginationCursor.decode_cursor(cursor)
        last_id = cursor_data["last_id"]
        last_ingested_at = cursor_data["last_created_at"]

    is_read = _news_item_is_read_clause(user_id=user_id)
    query = _visible_news_item_query(db, user_id=user_id).add_columns(is_read.label("is_read"))
    if read_filter == "unread":
        query = query.filter(~is_read)
    elif read_filter == "read":
        query = query.filter(is_read)

    if last_ingested_at is not None and last_id is not None:
        query = query.filter(
            or_(
                NewsItem.ingested_at < last_ingested_at,
                and_(NewsItem.ingested_at == last_ingested_at, NewsItem.id < last_id),
            )
        )

    rows = (
        query.order_by(NewsItem.ingested_at.desc(), NewsItem.id.desc()).limit(limit + 1).all()
    )
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    available_dates = sorted(
        {
            (_coerce_utc(item.published_at) or _coerce_utc(item.ingested_at) or datetime.now(UTC))
            .date()
            .isoformat()
            for item, _row_is_read in rows
        },
        reverse=True,
    )
    next_cursor = None
    if has_more and rows:
        last_item = rows[-1][0]
        next_cursor = PaginationCursor.encode_cursor(
            last_id=last_item.id,
            last_created_at=last_item.ingested_at,
            filters={"read_filter": read_filter},
        )

    return ContentListResponse(
        contents=[_present_summary(item, is_read=bool(row_is_read)) for item, row_is_read in rows],
        available_dates=available_dates,
        content_types=[ContentType.NEWS],
        meta=PaginationMetadata(
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=len(rows),
            total=len(rows),
        ),
    )


def get_visible_news_item_detail(
    db: Session,
    *,
    user_id: int,
    news_item_id: int,
) -> ContentDetailResponse | None:
    """Return one visible representative news item detail response."""
    is_read = _news_item_is_read_clause(user_id=user_id)
    row = (
        _visible_news_item_query(db, user_id=user_id)
        .add_columns(is_read.label("is_read"))
        .filter(NewsItem.id == news_item_id)
        .first()
    )
    if row is None:
        return None
    item, row_is_read = row
    return _present_detail(item, is_read=bool(row_is_read))


def get_visible_news_item(db: Session, *, user_id: int, news_item_id: int) -> NewsItem | None:
    """Return a visible representative news item row or ``None`` when inaccessible."""
    return (
        _visible_news_item_query(db, user_id=user_id)
        .filter(NewsItem.id == news_item_id)
        .first()
    )


def bulk_mark_news_items_read(
    db: Session,
    *,
    user_id: int,
    news_item_ids: list[int],
) -> dict[str, Any]:
    """Mark visible representative news items as read for one user."""
    requested_ids = list(news_item_ids)
    visible_ids = {
        row.id
        for row in _visible_news_item_query(db, user_id=user_id)
        .with_entities(NewsItem.id)
        .filter(NewsItem.id.in_(news_item_ids))
        .all()
    }
    if not visible_ids:
        return {
            "status": "success",
            "marked_count": 0,
            "failed_ids": requested_ids,
            "total_requested": len(requested_ids),
        }

    existing_ids = {
        row.news_item_id
        for row in db.query(NewsItemReadStatus.news_item_id)
        .filter(NewsItemReadStatus.user_id == user_id)
        .filter(NewsItemReadStatus.news_item_id.in_(visible_ids))
        .all()
    }
    now = datetime.now(UTC).replace(tzinfo=None)
    for news_item_id in sorted(visible_ids - existing_ids):
        db.add(NewsItemReadStatus(user_id=user_id, news_item_id=news_item_id, read_at=now))
    db.commit()
    return {
        "status": "success",
        "marked_count": len(visible_ids - existing_ids),
        "failed_ids": sorted(set(requested_ids) - visible_ids),
        "total_requested": len(requested_ids),
    }


def count_unread_news_items(db: Session, *, user_id: int) -> int:
    """Return the unread count for visible representative news items."""
    is_read = _news_item_is_read_clause(user_id=user_id)
    return int(
        _visible_news_item_query(db, user_id=user_id)
        .with_entities(func.count(NewsItem.id))
        .filter(~is_read)
        .scalar()
        or 0
    )
