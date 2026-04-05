"""News-item feed and conversion endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentDiscussion
from app.models.user import User
from app.queries.get_content_discussion import build_discussion_response
from app.models.api.common import (
    BulkMarkReadRequest,
    ContentDetailResponse,
    ContentDiscussionResponse,
    ContentListResponse,
)
from app.models.api.news import ConvertNewsItemResponse
from app.services.news_feed import (
    bulk_mark_news_items_read,
    get_visible_news_item,
    get_visible_news_item_detail,
    list_visible_news_items,
)
from app.services.queue import TaskType, get_queue_service
from app.utils.url_utils import is_http_url, normalize_http_url

router = APIRouter(tags=["news"], responses={404: {"description": "Not found"}})


@router.get("/items", response_model=ContentListResponse, summary="List visible news items")
def list_news_items(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    read_filter: Annotated[
        str,
        Query(pattern="^(all|read|unread)$", description="Filter by read status"),
    ] = "unread",
    cursor: Annotated[str | None, Query(description="Opaque cursor token")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> ContentListResponse:
    """Return the visible representative news feed for the current user."""
    return list_visible_news_items(
        db,
        user_id=current_user.id,
        read_filter=read_filter,
        cursor=cursor,
        limit=limit,
    )


@router.post("/items/mark-read", summary="Mark visible news items as read")
def mark_news_items_read(
    payload: BulkMarkReadRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    """Mark the given visible representative news items as read."""
    return bulk_mark_news_items_read(
        db,
        user_id=current_user.id,
        news_item_ids=payload.content_ids,
    )

@router.get(
    "/items/{news_item_id}",
    response_model=ContentDetailResponse,
    summary="Get one news item",
)
def get_news_item(
    news_item_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContentDetailResponse:
    """Return one visible representative news item."""
    item = get_visible_news_item_detail(db, user_id=current_user.id, news_item_id=news_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return item


@router.get(
    "/items/{news_item_id}/discussion",
    response_model=ContentDiscussionResponse,
    summary="Get one news item discussion",
)
def get_news_item_discussion(
    news_item_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContentDiscussionResponse:
    """Return discussion payload for one visible representative news item."""
    item = get_visible_news_item(db, user_id=current_user.id, news_item_id=news_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")

    discussion_row = None
    if item.legacy_content_id is not None:
        discussion_row = (
            db.query(ContentDiscussion)
            .filter(ContentDiscussion.content_id == item.legacy_content_id)
            .first()
        )

    raw_metadata = (
        item.raw_metadata
        if discussion_row is None and isinstance(item.raw_metadata, dict)
        else {}
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


@router.post(
    "/items/{news_item_id}/convert-to-article",
    response_model=ConvertNewsItemResponse,
    summary="Convert one news item into article content",
)
def convert_news_item_to_article(
    news_item_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConvertNewsItemResponse:
    """Convert one representative news item into article content."""
    item = get_visible_news_item(db, user_id=current_user.id, news_item_id=news_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")

    article_url = normalize_http_url(item.article_url or item.canonical_story_url)
    if not is_http_url(article_url):
        raise HTTPException(status_code=400, detail="No article URL found for news item")

    existing_article = (
        db.query(Content)
        .filter(Content.url == article_url, Content.content_type == ContentType.ARTICLE.value)
        .first()
    )
    if existing_article is not None:
        return ConvertNewsItemResponse(
            news_item_id=item.id,
            new_content_id=existing_article.id,
            already_exists=True,
            message="Article already exists in system",
        )

    new_article = Content(
        url=article_url,
        source_url=article_url,
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.PENDING.value,
        title=item.article_title,
        source=item.article_domain,
        platform=None,
        content_metadata={},
        classification=None,
    )
    db.add(new_article)
    try:
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if "UNIQUE constraint failed" in str(exc) or "duplicate key" in str(exc).lower():
            existing_article = (
                db.query(Content)
                .filter(
                    Content.url == article_url, Content.content_type == ContentType.ARTICLE.value
                )
                .first()
            )
            if existing_article is not None:
                return ConvertNewsItemResponse(
                    news_item_id=item.id,
                    new_content_id=existing_article.id,
                    already_exists=True,
                    message="Article already exists in system",
                )
        raise

    db.refresh(new_article)
    get_queue_service().enqueue(TaskType.PROCESS_CONTENT, content_id=new_article.id)
    return ConvertNewsItemResponse(
        news_item_id=item.id,
        new_content_id=new_article.id,
        already_exists=False,
        message="Article created and queued for processing",
    )
