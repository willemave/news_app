"""Application query for news-item discussion payloads."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.api.common import ContentDiscussionResponse
from app.models.schema import ContentDiscussion, NewsItem
from app.queries.get_content_discussion import build_discussion_response
from app.services.news_feed import get_visible_news_item


def build_response_for_news_item(
    db: Session,
    *,
    item: NewsItem,
) -> ContentDiscussionResponse:
    """Build discussion payload for one visible representative news item."""
    news_item_id = item.id
    if news_item_id is None:
        raise ValueError("News item is missing an id")

    discussion_row = None
    if item.legacy_content_id is not None:
        discussion_row = (
            db.query(ContentDiscussion)
            .filter(ContentDiscussion.content_id == item.legacy_content_id)
            .first()
        )

    raw_metadata = (
        item.raw_metadata if discussion_row is None and isinstance(item.raw_metadata, dict) else {}
    )
    embedded_discussion = raw_metadata.get("discussion_payload")
    if not isinstance(embedded_discussion, dict):
        embedded_discussion = None

    fallback_discussion_url = item.discussion_url or item.canonical_item_url
    return build_discussion_response(
        content_id=news_item_id,
        discussion_url=fallback_discussion_url,
        platform=item.platform,
        discussion_row=discussion_row,
        discussion_data=embedded_discussion,
        status=str(raw_metadata["discussion_status"])
        if raw_metadata.get("discussion_status")
        else None,
        error_message=str(raw_metadata["discussion_error"])
        if raw_metadata.get("discussion_error")
        else None,
        fetched_at=str(raw_metadata["discussion_fetched_at"])
        if raw_metadata.get("discussion_fetched_at")
        else None,
    )


def execute(db: Session, *, user_id: int, news_item_id: int) -> ContentDiscussionResponse:
    """Return discussion payload for one visible representative news item."""
    item = get_visible_news_item(
        db,
        user_id=user_id,
        news_item_id=news_item_id,
    )
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return build_response_for_news_item(db, item=item)
