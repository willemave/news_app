"""Content transformation and action endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.domain.converters import content_to_domain
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.models.user import User
from app.routers.api.models import (
    ConvertNewsResponse,
    TweetSuggestion,
    TweetSuggestionsRequest,
    TweetSuggestionsResponse,
)
from app.services.event_logger import log_event
from app.services.tweet_suggestions import generate_tweet_suggestions

router = APIRouter()


@router.post(
    "/{content_id}/convert-to-article",
    response_model=ConvertNewsResponse,
    summary="Convert news link to article",
    description=(
        "Convert a news content item to a full article by extracting the article URL "
        "from the news metadata and creating a new article content entry. "
        "If the article already exists, returns the existing article ID."
    ),
    responses={
        200: {"description": "News link converted successfully"},
        400: {"description": "Content cannot be converted (not news or no article URL)"},
        404: {"description": "Content not found"},
    },
)
async def convert_news_to_article(
    content_id: Annotated[int, Path(..., description="News content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ConvertNewsResponse:
    """Convert a news link to a full article content entry.

    Extracts the article URL from the news metadata and creates a new
    article content entry for processing. If an article with that URL
    already exists, returns the existing article ID instead of creating
    a duplicate.
    """
    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Verify content is news type
    if content.content_type != ContentType.NEWS.value:
        raise HTTPException(
            status_code=400, detail="Only news content can be converted to articles"
        )

    # Extract article URL from metadata
    metadata = content.content_metadata or {}
    article_meta = metadata.get("article", {})
    article_url = article_meta.get("url")

    if not article_url:
        raise HTTPException(status_code=400, detail="No article URL found in news metadata")

    # Check if article with this URL already exists (UNIQUE constraint on url + content_type)
    existing_article = (
        db.query(Content)
        .filter(Content.url == article_url)
        .filter(Content.content_type == ContentType.ARTICLE.value)
        .first()
    )

    if existing_article:
        return ConvertNewsResponse(
            status="success",
            new_content_id=existing_article.id,
            original_content_id=content_id,
            already_exists=True,
            message="Article already exists in system",
        )

    # Create new article content entry
    article_title = article_meta.get("title")
    source_domain = article_meta.get("source_domain")

    new_article = Content(
        url=article_url,
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.PENDING.value,
        title=article_title,
        source=source_domain,
        platform=None,  # Will be determined during processing
        content_metadata={},
        classification=None,
    )

    db.add(new_article)

    # Wrap commit in try/except to catch race conditions
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        # Check if it's a UNIQUE constraint error
        if "UNIQUE constraint failed" in str(e) or "duplicate key" in str(e).lower():
            # Race condition: another request created this article between our check and insert
            # Query again to get the existing article
            existing_article = (
                db.query(Content)
                .filter(Content.url == article_url)
                .filter(Content.content_type == ContentType.ARTICLE.value)
                .first()
            )
            if existing_article:
                return ConvertNewsResponse(
                    status="success",
                    new_content_id=existing_article.id,
                    original_content_id=content_id,
                    already_exists=True,
                    message="Article already exists in system",
                )
        # Re-raise all exceptions (including non-duplicate constraint errors)
        raise

    db.refresh(new_article)

    return ConvertNewsResponse(
        status="success",
        new_content_id=new_article.id,
        original_content_id=content_id,
        already_exists=False,
        message="Article created and queued for processing",
    )


@router.post(
    "/{content_id}/tweet-suggestions",
    response_model=TweetSuggestionsResponse,
    summary="Generate tweet suggestions for content",
    description=(
        "Generate 3 tweet suggestions for a content item using Gemini. "
        "Supports all content types. Requires JWT authentication."
    ),
    responses={
        200: {"description": "Tweet suggestions generated successfully"},
        400: {"description": "Content not ready or unsupported type"},
        404: {"description": "Content not found"},
        502: {"description": "LLM generation failed"},
    },
)
async def get_tweet_suggestions(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    request: TweetSuggestionsRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TweetSuggestionsResponse:
    """Generate tweet suggestions for content.

    Calls Gemini to generate 3 tweet suggestions based on the content's
    title, summary, and key points. Supports all content types.

    Args:
        content_id: ID of the content to generate tweets for
        request: Request body with optional message and creativity level
        db: Database session
        current_user: Authenticated user

    Returns:
        TweetSuggestionsResponse with 3 tweet suggestions
    """
    # Load content
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Validate content status
    if content.status != ContentStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400,
            detail=f"Content not ready for tweets (status: {content.status})",
        )

    # Convert to domain model
    content_data = content_to_domain(content)

    # Generate tweet suggestions off the event loop to avoid asyncio loop conflicts
    result = await run_in_threadpool(
        generate_tweet_suggestions,
        content=content_data,
        message=request.message,
        creativity=request.creativity,
    )

    if result is None:
        # Log the failure
        log_event(
            event_type="tweet_suggestions",
            event_name="generation_failed",
            status="failed",
            content_id=content_id,
            user_id=current_user.id,
            creativity=request.creativity,
        )
        raise HTTPException(
            status_code=502,
            detail="Tweet generation failed. Please try again.",
        )

    # Log success
    log_event(
        event_type="tweet_suggestions",
        event_name="generation_success",
        status="completed",
        content_id=content_id,
        user_id=current_user.id,
        creativity=request.creativity,
        model=result.model,
    )

    # Convert result to response
    return TweetSuggestionsResponse(
        content_id=result.content_id,
        creativity=result.creativity,
        model=result.model,
        suggestions=[
            TweetSuggestion(
                id=s.id,
                text=s.text,
                style_label=s.style_label,
            )
            for s in result.suggestions
        ],
    )
