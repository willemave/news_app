"""Content transformation and action endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.routers.api.models import ConvertNewsResponse

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
