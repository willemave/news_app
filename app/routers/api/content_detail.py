"""Content detail and chat URL endpoints."""

from typing import Annotated
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.constants import SELF_SUBMISSION_SOURCE
from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.timing import timed
from app.domain.converters import content_to_domain
from app.models.metadata import ContentType
from app.models.schema import Content, ContentFavorites, ContentReadStatus
from app.models.user import User
from app.routers.api.content_list import get_content_image_url, get_content_thumbnail_url
from app.routers.api.models import ChatGPTUrlResponse, ContentDetailResponse, DetectedFeed

router = APIRouter()


@router.get(
    "/{content_id}",
    response_model=ContentDetailResponse,
    summary="Get content details",
    description="Retrieve detailed information about a specific content item.",
    responses={
        404: {
            "description": "Content not found",
            "content": {"application/json": {"example": {"detail": "Content not found"}}},
        }
    },
)
def get_content_detail(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContentDetailResponse:
    """Get detailed view of a specific content item."""
    is_read_subquery = exists(
        select(ContentReadStatus.id).where(
            ContentReadStatus.user_id == current_user.id,
            ContentReadStatus.content_id == Content.id,
        )
    )
    is_favorited_subquery = exists(
        select(ContentFavorites.id).where(
            ContentFavorites.user_id == current_user.id,
            ContentFavorites.content_id == Content.id,
        )
    )

    with timed("query content_detail"):
        row = (
            db.query(
                Content,
                is_read_subquery.label("is_read"),
                is_favorited_subquery.label("is_favorited"),
            )
            .filter(Content.id == content_id)
            .first()
        )

    if not row:
        raise HTTPException(status_code=404, detail="Content not found")

    content, is_read, is_favorited = row

    # Convert to domain object to validate metadata
    try:
        domain_content = content_to_domain(content)
    except Exception as e:
        # If domain conversion fails, raise HTTP exception
        raise HTTPException(
            status_code=500, detail=f"Failed to process content metadata: {str(e)}"
        ) from e

    structured_summary = domain_content.structured_summary
    bullet_points = domain_content.bullet_points
    quotes = domain_content.quotes
    topics = domain_content.topics
    full_markdown = domain_content.full_markdown
    rendered_markdown = domain_content.rendered_news_markdown
    news_items = domain_content.news_items
    news_article_url = None
    news_discussion_url = None
    news_key_points = None
    news_summary_text = domain_content.summary

    if domain_content.content_type == ContentType.NEWS:
        metadata = domain_content.metadata or {}
        article_meta = metadata.get("article", {})
        aggregator_meta = metadata.get("aggregator", {})
        summary_meta = metadata.get("summary", {})

        news_article_url = article_meta.get("url")
        news_discussion_url = aggregator_meta.get("url")
        key_points = summary_meta.get("bullet_points")
        if key_points:
            news_key_points = [
                point["text"] if isinstance(point, dict) else point for point in key_points
            ]
        news_summary_text = (
            summary_meta.get("overview")
            or summary_meta.get("summary")
            or summary_meta.get("hook")
            or summary_meta.get("takeaway")
            or domain_content.summary
        )
        structured_summary = None
        bullet_points = []
        quotes = []
        topics = []
        full_markdown = None
        rendered_markdown = None
        news_items = []

    # Extract detected feed from metadata if present
    detected_feed = None
    detected_feed_data = (domain_content.metadata or {}).get("detected_feed")
    if detected_feed_data:
        detected_feed = DetectedFeed(
            url=detected_feed_data["url"],
            type=detected_feed_data["type"],
            title=detected_feed_data.get("title"),
            format=detected_feed_data.get("format", "rss"),
        )
    can_subscribe = False
    if detected_feed_data and (
        domain_content.content_type == ContentType.NEWS
        or domain_content.source == SELF_SUBMISSION_SOURCE
    ):
        from app.services.feed_subscription import can_subscribe_to_feed

        can_subscribe = can_subscribe_to_feed(db, current_user.id, detected_feed_data)

    # Return the validated content with all properties from ContentData
    return ContentDetailResponse(
        id=domain_content.id,
        content_type=domain_content.content_type.value,
        url=str(domain_content.url),
        title=domain_content.title,
        display_title=domain_content.display_title,
        source=domain_content.source,
        status=domain_content.status.value,
        error_message=domain_content.error_message,
        retry_count=domain_content.retry_count,
        metadata=domain_content.metadata,
        created_at=domain_content.created_at.isoformat() if domain_content.created_at else "",
        updated_at=content.updated_at.isoformat() if content.updated_at else None,
        processed_at=domain_content.processed_at.isoformat()
        if domain_content.processed_at
        else None,
        checked_out_by=content.checked_out_by,
        checked_out_at=content.checked_out_at.isoformat() if content.checked_out_at else None,
        publication_date=domain_content.publication_date.isoformat()
        if domain_content.publication_date
        else None,
        is_read=bool(is_read),
        is_favorited=bool(is_favorited),
        # Additional properties from ContentData
        summary=news_summary_text,
        short_summary=news_summary_text,
        structured_summary=structured_summary,
        bullet_points=bullet_points,
        quotes=quotes,
        topics=topics,
        full_markdown=full_markdown,
        is_aggregate=domain_content.is_aggregate,
        rendered_markdown=rendered_markdown,
        news_items=news_items,
        news_article_url=news_article_url,
        news_discussion_url=news_discussion_url,
        news_key_points=news_key_points,
        news_summary=news_summary_text,
        image_url=get_content_image_url(domain_content),
        thumbnail_url=get_content_thumbnail_url(domain_content.id),
        detected_feed=detected_feed,
        can_subscribe=can_subscribe,
    )


@router.get(
    "/{content_id}/chat-url",
    response_model=ChatGPTUrlResponse,
    summary="Get ChatGPT URL for content",
    description="Generate a URL to open ChatGPT with the content's full text for discussion.",
    responses={
        404: {"description": "Content not found"},
    },
)
def get_chatgpt_url(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    user_prompt: Annotated[
        str | None,
        Query(max_length=2000, description="Optional user prompt to prepend to chat"),
    ] = None,
) -> ChatGPTUrlResponse:
    """Generate ChatGPT URL for chatting about the content.

    If ``user_prompt`` is provided, it is prepended to the generated prompt so the
    selection the user made in the UI appears as the first message in ChatGPT.
    """
    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    try:
        domain_content = content_to_domain(content)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process content metadata: {str(e)}"
        ) from e

    # Build the prompt with context
    prompt_parts = []

    if user_prompt:
        prompt_parts.append("USER PROMPT:")
        prompt_parts.append(user_prompt.strip())
        prompt_parts.append("")

    # Add title and source context
    prompt_parts.append(f"I'd like to discuss this {domain_content.content_type.value}:")
    prompt_parts.append(f"Title: {domain_content.display_title}")

    if domain_content.source:
        prompt_parts.append(f"Source: {domain_content.source}")

    if domain_content.publication_date:
        prompt_parts.append(f"Published: {domain_content.publication_date.strftime('%B %d, %Y')}")

    prompt_parts.append("")  # Empty line for separation

    # Add the main content
    if domain_content.content_type.value == "podcast" and domain_content.transcript:
        prompt_parts.append("TRANSCRIPT:")
        content_text = domain_content.transcript
    elif domain_content.full_markdown:
        prompt_parts.append("ARTICLE:")
        content_text = domain_content.full_markdown
    elif domain_content.summary:
        prompt_parts.append("SUMMARY:")
        content_text = domain_content.summary
    else:
        # Fallback to structured summary if available
        if domain_content.structured_summary:
            prompt_parts.append("KEY POINTS:")
            if domain_content.bullet_points:
                for bullet in domain_content.bullet_points:
                    prompt_parts.append(f"• {bullet.get('text', '')}")
            if domain_content.quotes:
                prompt_parts.append("\nQUOTES:")
                for quote in domain_content.quotes:
                    prompt_parts.append(f'"{quote.get("text", "")}"')
                    if quote.get("context"):
                        prompt_parts.append(f"  - {quote['context']}")
        content_text = ""

    # Combine all parts
    full_prompt = "\n".join(prompt_parts)

    # Add content text if available
    if content_text:
        full_prompt += "\n" + content_text

    # URL length limit (conservative estimate for browser compatibility)
    max_url_length = 8000
    base_url = "https://chat.openai.com/?q="

    # Check if we need to truncate
    truncated = False
    encoded_prompt = quote_plus(full_prompt)
    full_url = base_url + encoded_prompt

    if len(full_url) > max_url_length:
        # Truncate the content to fit
        truncated = True
        available_space = max_url_length - len(base_url) - 100  # Leave some buffer

        # Try to keep the context and truncate the content
        context_part = "\n".join(prompt_parts)
        encoded_context = quote_plus(context_part)

        if len(encoded_context) < available_space:
            # Add as much content as possible
            remaining_space = available_space - len(encoded_context)
            truncated_content = content_text[: remaining_space // 3]  # Rough estimate for encoding
            truncated_prompt = (
                context_part
                + "\n"
                + truncated_content
                + "\n\n[Content truncated for URL length...]"
            )
        else:
            # Even context is too long, just use title and basic info
            truncated_prompt = f"Chat about: {domain_content.display_title}"
            if domain_content.source:
                truncated_prompt += f" from {domain_content.source}"

        encoded_prompt = quote_plus(truncated_prompt)
        full_url = base_url + encoded_prompt

    return ChatGPTUrlResponse(chat_url=full_url, truncated=truncated)
