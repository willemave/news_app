"""News-native digest and item endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.db import get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, NewsDigest, NewsDigestBullet, NewsItem
from app.models.user import User
from app.routers.api.chat_models import (
    ChatMessageDto,
    ChatMessageRole,
    ChatSessionSummaryDto,
    StartDailyDigestChatResponse,
)
from app.routers.api.chat_models import MessageProcessingStatus as MessageProcessingStatusDto
from app.routers.api.news_models import (
    ConvertNewsItemResponse,
    NewsDigestBulletResponse,
    NewsDigestCitationResponse,
    NewsDigestListResponse,
    NewsDigestResponse,
    NewsItemResponse,
)
from app.services.chat_agent import process_message_async
from app.services.news_chat import start_news_digest_bullet_chat
from app.services.news_digests import (
    get_user_news_digest,
    get_visible_news_item,
    list_digest_bullets_with_sources,
    list_news_digests,
    resolve_news_item_outward_url,
)
from app.services.queue import TaskType, get_queue_service
from app.utils.url_utils import is_http_url, normalize_http_url

router = APIRouter(tags=["news"], responses={404: {"description": "Not found"}})


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _build_news_item_response(item: NewsItem) -> NewsItemResponse:
    key_points = item.summary_key_points if isinstance(item.summary_key_points, list) else []
    normalized_key_points = [
        str(raw.get("text") if isinstance(raw, dict) else raw).strip()
        for raw in key_points
        if str(raw.get("text") if isinstance(raw, dict) else raw).strip()
    ]
    return NewsItemResponse(
        id=item.id,
        visibility_scope=item.visibility_scope,
        owner_user_id=item.owner_user_id,
        platform=item.platform,
        source_type=item.source_type,
        source_label=item.source_label,
        source_external_id=item.source_external_id,
        canonical_item_url=item.canonical_item_url,
        canonical_story_url=item.canonical_story_url,
        article_url=item.article_url,
        article_title=item.article_title,
        article_domain=item.article_domain,
        discussion_url=item.discussion_url,
        summary_title=item.summary_title,
        summary_key_points=normalized_key_points,
        summary_text=item.summary_text,
        status=item.status,
        published_at=item.published_at,
        ingested_at=item.ingested_at,
        processed_at=item.processed_at,
        raw_metadata=dict(item.raw_metadata or {}),
    )


def _build_digest_response(db: Session, digest: NewsDigest) -> NewsDigestResponse:
    bullet_rows = list_digest_bullets_with_sources(db, digest_id=digest.id)
    bullets: list[NewsDigestBulletResponse] = []
    for bullet, cited_items in bullet_rows:
        citations = [
            NewsDigestCitationResponse(
                news_item_id=item.id,
                label=item.source_label,
                title=item.summary_title or item.article_title or f"News item {item.id}",
                url=resolve_news_item_outward_url(item),
                article_url=item.article_url,
            )
            for item in cited_items
        ]
        bullets.append(
            NewsDigestBulletResponse(
                id=bullet.id,
                position=bullet.position,
                topic=bullet.topic,
                details=bullet.details,
                source_count=bullet.source_count,
                citations=citations,
            )
        )

    return NewsDigestResponse(
        id=digest.id,
        timezone=digest.timezone,
        title=digest.title,
        summary=digest.summary,
        source_count=digest.source_count,
        group_count=digest.group_count,
        trigger_reason=digest.trigger_reason,
        is_read=digest.read_at is not None,
        read_at=digest.read_at,
        generated_at=digest.generated_at,
        window_start_at=digest.window_start_at,
        window_end_at=digest.window_end_at,
        bullets=bullets,
    )


def _get_user_digest_or_404(
    db: Session,
    *,
    user_id: int,
    digest_id: int,
) -> NewsDigest:
    digest = get_user_news_digest(db, user_id=user_id, digest_id=digest_id)
    if digest is None:
        raise HTTPException(status_code=404, detail="News digest not found")
    return digest


@router.get("/digests", response_model=NewsDigestListResponse, summary="List news digest runs")
def list_user_news_digests(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    read_filter: Annotated[
        str,
        Query(pattern="^(all|read|unread)$", description="Filter by read status"),
    ] = "unread",
    cursor: Annotated[str | None, Query(description="Opaque cursor token")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> NewsDigestListResponse:
    digests, meta = list_news_digests(
        db,
        user_id=current_user.id,
        read_filter=read_filter,
        cursor=cursor,
        limit=limit,
    )
    return NewsDigestListResponse(
        digests=[_build_digest_response(db, digest) for digest in digests],
        meta=meta,
    )


@router.get("/digests/{digest_id}", response_model=NewsDigestResponse, summary="Get one digest run")
def get_news_digest(
    digest_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NewsDigestResponse:
    digest = _get_user_digest_or_404(db, user_id=current_user.id, digest_id=digest_id)
    return _build_digest_response(db, digest)


@router.post(
    "/digests/{digest_id}/mark-read",
    summary="Mark one digest run as read",
)
def mark_news_digest_read(
    digest_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict[str, Any]:
    digest = _get_user_digest_or_404(db, user_id=current_user.id, digest_id=digest_id)
    digest.read_at = _utcnow_naive()
    db.commit()
    return {
        "status": "success",
        "digest_id": digest.id,
        "is_read": True,
        "read_at": digest.read_at,
    }


@router.post(
    "/digests/{digest_id}/bullets/{bullet_id}/dig-deeper",
    response_model=StartDailyDigestChatResponse,
    summary="Start a bullet-focused news digest chat",
)
async def start_news_digest_bullet_dig_deeper(
    digest_id: Annotated[int, Path(..., gt=0)],
    bullet_id: Annotated[int, Path(..., gt=0)],
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> StartDailyDigestChatResponse:
    digest = _get_user_digest_or_404(db, user_id=current_user.id, digest_id=digest_id)
    bullet = (
        db.query(NewsDigestBullet)
        .filter(NewsDigestBullet.id == bullet_id, NewsDigestBullet.digest_id == digest.id)
        .first()
    )
    if bullet is None:
        raise HTTPException(status_code=404, detail="News digest bullet not found")

    session, db_message, prompt = start_news_digest_bullet_chat(
        db,
        digest=digest,
        bullet=bullet,
        user_id=current_user.id,
    )
    background_tasks.add_task(process_message_async, session.id, db_message.id, prompt)

    return StartDailyDigestChatResponse(
        session=ChatSessionSummaryDto(
            id=session.id,
            title=session.title,
            content_id=session.content_id,
            session_type=session.session_type,
            topic=session.topic,
            llm_model=session.llm_model,
            llm_provider=session.llm_provider,
            created_at=session.created_at,
            updated_at=session.updated_at,
            last_message_at=session.last_message_at,
            is_archived=session.is_archived,
            article_title=None,
            article_url=None,
            article_summary=None,
            article_source=None,
            has_pending_message=True,
            is_favorite=False,
            has_messages=True,
            last_message_preview=None,
            last_message_role=None,
        ),
        user_message=ChatMessageDto(
            id=db_message.id,
            session_id=session.id,
            role=ChatMessageRole.USER,
            content=prompt,
            timestamp=db_message.created_at,
            status=MessageProcessingStatusDto.PROCESSING,
        ),
        message_id=db_message.id,
        status=MessageProcessingStatusDto.PROCESSING,
    )


@router.get("/items/{news_item_id}", response_model=NewsItemResponse, summary="Get one news item")
def get_news_item(
    news_item_id: Annotated[int, Path(..., gt=0)],
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> NewsItemResponse:
    item = get_visible_news_item(db, user_id=current_user.id, news_item_id=news_item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return _build_news_item_response(item)


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
