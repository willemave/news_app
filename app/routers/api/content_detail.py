"""Content detail and chat URL endpoints."""

from typing import Annotated
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.core.db import get_readonly_db_session
from app.core.deps import get_current_user
from app.core.timing import timed
from app.models.schema import Content, ContentDiscussion
from app.models.user import User
from app.presenters.content_presenter import (
    build_content_detail_response,
    build_domain_content,
    can_subscribe_for_feed,
)
from app.repositories.content_repository import build_visibility_context
from app.routers.api.models import (
    ChatGPTUrlResponse,
    ContentDetailResponse,
    ContentDiscussionResponse,
    DiscussionCommentResponse,
    DiscussionGroupResponse,
    DiscussionItemResponse,
    DiscussionLinkResponse,
)

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
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContentDetailResponse:
    """Get detailed view of a specific content item."""
    context = build_visibility_context(current_user.id)

    with timed("query content_detail"):
        row = (
            db.query(
                Content,
                context.is_read.label("is_read"),
                context.is_favorited.label("is_favorited"),
            )
            .filter(Content.id == content_id)
            .first()
        )

    if not row:
        raise HTTPException(status_code=404, detail="Content not found")

    content, is_read, is_favorited = row

    # Convert to domain object to validate metadata
    try:
        domain_content = build_domain_content(content)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to process content metadata: {str(e)}"
        ) from e

    detected_feed_data = (domain_content.metadata or {}).get("detected_feed")
    can_subscribe = False
    if can_subscribe_for_feed(domain_content, detected_feed_data):
        from app.services.feed_subscription import can_subscribe_to_feed

        can_subscribe = can_subscribe_to_feed(db, current_user.id, detected_feed_data)

    return build_content_detail_response(
        content=content,
        domain_content=domain_content,
        is_read=bool(is_read),
        is_favorited=bool(is_favorited),
        detected_feed_data=detected_feed_data,
        can_subscribe=can_subscribe,
    )


def _build_discussion_response(
    *,
    content_id: int,
    discussion_url: str | None,
    platform: str | None,
    discussion_row: ContentDiscussion | None,
) -> ContentDiscussionResponse:
    """Build a typed discussion response payload."""
    if discussion_row is None:
        return ContentDiscussionResponse(
            content_id=content_id,
            status="not_ready",
            mode="none",
            platform=platform,
            source_url=discussion_url,
            discussion_url=discussion_url,
            fetched_at=None,
            error_message=None,
            comments=[],
            discussion_groups=[],
            links=[],
            stats={},
        )

    data = (
        discussion_row.discussion_data
        if isinstance(discussion_row.discussion_data, dict)
        else {}
    )
    mode = (
        data.get("mode")
        if data.get("mode") in {"none", "comments", "discussion_list"}
        else "none"
    )

    comments: list[DiscussionCommentResponse] = []
    for entry in data.get("comments", []):
        if not isinstance(entry, dict):
            continue
        comment_id = str(entry.get("comment_id") or "").strip()
        if not comment_id:
            continue
        comments.append(
            DiscussionCommentResponse(
                comment_id=comment_id,
                parent_id=str(entry.get("parent_id")) if entry.get("parent_id") else None,
                author=str(entry.get("author")) if entry.get("author") else None,
                text=str(entry.get("text") or ""),
                compact_text=str(entry.get("compact_text"))
                if entry.get("compact_text")
                else None,
                depth=int(entry.get("depth") or 0),
                created_at=str(entry.get("created_at")) if entry.get("created_at") else None,
                source_url=str(entry.get("source_url")) if entry.get("source_url") else None,
            )
        )

    groups: list[DiscussionGroupResponse] = []
    for raw_group in data.get("discussion_groups", []):
        if not isinstance(raw_group, dict):
            continue
        label = str(raw_group.get("label") or "").strip()
        if not label:
            continue

        items: list[DiscussionItemResponse] = []
        for raw_item in raw_group.get("items", []):
            if not isinstance(raw_item, dict):
                continue
            url = str(raw_item.get("url") or "").strip()
            if not url:
                continue
            title = str(raw_item.get("title") or url)
            items.append(DiscussionItemResponse(title=title, url=url))
        groups.append(DiscussionGroupResponse(label=label, items=items))

    links: list[DiscussionLinkResponse] = []
    for raw_link in data.get("links", []):
        if not isinstance(raw_link, dict):
            continue
        url = str(raw_link.get("url") or "").strip()
        if not url:
            continue
        links.append(
            DiscussionLinkResponse(
                url=url,
                source=str(raw_link.get("source") or "unknown"),
                comment_id=str(raw_link.get("comment_id")) if raw_link.get("comment_id") else None,
                group_label=str(raw_link.get("group_label"))
                if raw_link.get("group_label")
                else None,
                title=str(raw_link.get("title")) if raw_link.get("title") else None,
            )
        )

    source_url = str(data.get("source_url")) if data.get("source_url") else discussion_url
    return ContentDiscussionResponse(
        content_id=content_id,
        status=discussion_row.status,
        mode=mode,
        platform=discussion_row.platform or platform,
        source_url=source_url,
        discussion_url=discussion_url,
        fetched_at=discussion_row.fetched_at.isoformat() if discussion_row.fetched_at else None,
        error_message=discussion_row.error_message,
        comments=comments,
        discussion_groups=groups,
        links=links,
        stats=data.get("stats") if isinstance(data.get("stats"), dict) else {},
    )


@router.get(
    "/{content_id}/discussion",
    response_model=ContentDiscussionResponse,
    summary="Get discussion payload for a content item",
    description=(
        "Return in-app discussion data for the content item. Techmeme items return grouped "
        "discussion links. Hacker News and Reddit items return normalized comments + links."
    ),
    responses={
        404: {
            "description": "Content not found",
            "content": {"application/json": {"example": {"detail": "Content not found"}}},
        }
    },
)
def get_content_discussion(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ContentDiscussionResponse:
    """Return stored discussion payload for a content item."""
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    metadata = content.content_metadata if isinstance(content.content_metadata, dict) else {}
    discussion_url = metadata.get("discussion_url")
    platform = metadata.get("platform") or content.platform

    discussion_row = (
        db.query(ContentDiscussion).filter(ContentDiscussion.content_id == content_id).first()
    )

    return _build_discussion_response(
        content_id=content_id,
        discussion_url=str(discussion_url) if discussion_url else None,
        platform=str(platform) if platform else None,
        discussion_row=discussion_row,
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
    db: Annotated[Session, Depends(get_readonly_db_session)],
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
        domain_content = build_domain_content(content)
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
