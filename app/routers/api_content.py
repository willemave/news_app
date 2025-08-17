"""API endpoints for content with OpenAPI documentation."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.converters import content_to_domain
from app.models.metadata import ContentType
from app.models.schema import Content

router = APIRouter(
    tags=["content"],
    responses={404: {"description": "Not found"}},
)


# Response models for OpenAPI
class ContentSummaryResponse(BaseModel):
    """Summary information for a content item in list view."""

    id: int = Field(..., description="Unique identifier")
    content_type: str = Field(..., description="Type of content (article/podcast)")
    url: str = Field(..., description="Original URL of the content")
    title: str | None = Field(None, description="Content title")
    source: str | None = Field(
        None, description="Content source (e.g., substack name, podcast name)"
    )
    status: str = Field(..., description="Processing status")
    short_summary: str | None = Field(None, description="Short summary (max 200 chars)")
    created_at: str = Field(..., description="ISO timestamp when content was created")
    processed_at: str | None = Field(None, description="ISO timestamp when content was processed")
    classification: str | None = Field(None, description="Content classification (to_read/skip)")
    publication_date: str | None = Field(
        None, description="ISO timestamp of when content was published"
    )
    is_read: bool = Field(False, description="Whether the content has been marked as read")
    is_favorited: bool = Field(False, description="Whether the content has been favorited")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "content_type": "article",
                "url": "https://example.com/article",
                "title": "Understanding AI in 2025",
                "source": "Tech Blog",
                "status": "completed",
                "short_summary": "This article explores the latest developments in AI...",
                "created_at": "2025-06-19T10:30:00Z",
                "processed_at": "2025-06-19T10:35:00Z",
                "classification": "to_read",
                "publication_date": "2025-06-18T12:00:00Z",
                "is_read": False,
            }
        }


class ContentListResponse(BaseModel):
    """Response for content list endpoint."""

    contents: list[ContentSummaryResponse] = Field(..., description="List of content items")
    total: int = Field(..., description="Total number of items")
    available_dates: list[str] = Field(..., description="List of available dates (YYYY-MM-DD)")
    content_types: list[str] = Field(..., description="Available content types for filtering")

    class Config:
        json_schema_extra = {
            "example": {
                "contents": [
                    {
                        "id": 123,
                        "content_type": "article",
                        "url": "https://example.com/article",
                        "title": "Understanding AI in 2025",
                        "source": "Tech Blog",
                        "status": "completed",
                        "short_summary": "This article explores...",
                        "created_at": "2025-06-19T10:30:00Z",
                        "processed_at": "2025-06-19T10:35:00Z",
                        "classification": "to_read",
                    }
                ],
                "total": 1,
                "available_dates": ["2025-06-19", "2025-06-18"],
                "content_types": ["article", "podcast"],
            }
        }


class ContentDetailResponse(BaseModel):
    """Detailed response for a single content item."""

    id: int = Field(..., description="Unique identifier")
    content_type: str = Field(..., description="Type of content (article/podcast)")
    url: str = Field(..., description="Original URL of the content")
    title: str | None = Field(None, description="Content title")
    display_title: str = Field(
        ..., description="Display title (prefers summary title over content title)"
    )
    source: str | None = Field(None, description="Content source")
    status: str = Field(..., description="Processing status")
    error_message: str | None = Field(None, description="Error message if processing failed")
    retry_count: int = Field(..., description="Number of retry attempts")
    metadata: dict[str, Any] = Field(..., description="Content-specific metadata")
    created_at: str = Field(..., description="ISO timestamp when content was created")
    updated_at: str | None = Field(None, description="ISO timestamp of last update")
    processed_at: str | None = Field(None, description="ISO timestamp when content was processed")
    checked_out_by: str | None = Field(None, description="Worker ID that checked out this content")
    checked_out_at: str | None = Field(
        None, description="ISO timestamp when content was checked out"
    )
    publication_date: str | None = Field(
        None, description="ISO timestamp of when content was published"
    )
    is_read: bool = Field(False, description="Whether the content has been marked as read")
    is_favorited: bool = Field(False, description="Whether the content has been favorited")
    # Additional useful properties from ContentData
    summary: str | None = Field(None, description="Summary text")
    short_summary: str | None = Field(None, description="Short version of summary for list view")
    structured_summary: dict[str, Any] | None = Field(
        None, description="Structured summary with bullet points and quotes"
    )
    bullet_points: list[dict[str, str]] = Field(
        ..., description="Bullet points from structured summary"
    )
    quotes: list[dict[str, str]] = Field(..., description="Quotes from structured summary")
    topics: list[str] = Field(..., description="Topics from structured summary")
    full_markdown: str | None = Field(
        None, description="Full article content formatted as markdown"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "content_type": "article",
                "url": "https://example.com/article",
                "title": "Understanding AI in 2025",
                "source": "Tech Blog",
                "status": "completed",
                "error_message": None,
                "retry_count": 0,
                "metadata": {
                    "source": "Tech Blog",
                    "author": "Jane Doe",
                    "publication_date": "2025-06-19T00:00:00Z",
                    "content_type": "html",
                    "word_count": 1500,
                    "summary": {
                        "title": "Understanding AI in 2025",
                        "overview": "This article explores the latest developments...",
                        "bullet_points": [
                            {"text": "AI is transforming industries", "category": "key_finding"}
                        ],
                        "quotes": [{"text": "The future is now", "context": "Jane Doe"}],
                        "topics": ["AI", "Technology", "Future"],
                        "summarization_date": "2025-06-19T10:35:00Z",
                        "classification": "to_read",
                    },
                },
                "created_at": "2025-06-19T10:30:00Z",
                "updated_at": "2025-06-19T10:35:00Z",
                "processed_at": "2025-06-19T10:35:00Z",
                "checked_out_by": None,
                "checked_out_at": None,
                "publication_date": "2025-06-18T12:00:00Z",
                "is_read": False,
                "display_title": "Understanding AI in 2025",
                "summary": "This article explores the latest developments...",
                "short_summary": "This article explores the latest developments...",
                "structured_summary": {
                    "title": "Understanding AI in 2025",
                    "overview": "This article explores the latest developments...",
                    "bullet_points": [
                        {"text": "AI is transforming industries", "category": "key_finding"}
                    ],
                    "quotes": [{"text": "The future is now", "context": "Jane Doe"}],
                    "topics": ["AI", "Technology", "Future"],
                    "summarization_date": "2025-06-19T10:35:00Z",
                    "classification": "to_read",
                },
                "bullet_points": [
                    {"text": "AI is transforming industries", "category": "key_finding"}
                ],
                "quotes": [{"text": "The future is now", "context": "Jane Doe"}],
                "topics": ["AI", "Technology", "Future"],
                "full_markdown": "# Understanding AI in 2025\n\nFull article content...",
            }
        }


# Request models
class BulkMarkReadRequest(BaseModel):
    """Request to mark multiple content items as read."""

    content_ids: list[int] = Field(
        ..., description="List of content IDs to mark as read", min_items=1
    )

    class Config:
        json_schema_extra = {"example": {"content_ids": [123, 456, 789]}}


@router.get(
    "/",
    response_model=ContentListResponse,
    summary="List content items",
    description=(
        "Retrieve a list of content items with optional filtering by content type and date."
    ),
)
async def list_contents(
    content_type: str | None = Query(None, description="Filter by content type (article/podcast)"),
    date: str | None = Query(
        None,
        description="Filter by date (YYYY-MM-DD format)",
        regex="^\\d{4}-\\d{2}-\\d{2}$",
    ),
    read_filter: str = Query(
        "all",
        description="Filter by read status (all/read/unread)",
        regex="^(all|read|unread)$",
    ),
    db: Session = Depends(get_db_session),
) -> ContentListResponse:
    """List content with optional filters."""
    from app.services import read_status, favorites

    # Get read content IDs first
    read_content_ids = read_status.get_read_content_ids(db)
    
    # Get favorited content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db)

    # Get available dates for the dropdown
    available_dates_query = (
        db.query(func.date(Content.created_at).label("date"))
        .filter(
            Content.content_metadata["summary"].is_not(None)
            & (Content.content_metadata["summary"] != "null")
        )
        .filter((Content.classification != "skip") | (Content.classification.is_(None)))
        .distinct()
        .order_by(func.date(Content.created_at).desc())
    )

    available_dates = []
    for row in available_dates_query.all():
        if row.date:
            if isinstance(row.date, str):
                available_dates.append(row.date)
            else:
                available_dates.append(row.date.strftime("%Y-%m-%d"))

    # Query content
    query = db.query(Content)

    # Filter out "skip" classification articles
    query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))

    # Only show content that has been summarized (match HTML view)
    query = query.filter(
        Content.content_metadata["summary"].is_not(None)
        & (Content.content_metadata["summary"] != "null")
    )

    # Apply content type filter
    if content_type and content_type != "all":
        query = query.filter(Content.content_type == content_type)

    # Apply date filter
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(Content.created_at) == filter_date)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid date format") from e

    # Order by most recent first
    contents = query.order_by(Content.created_at.desc()).all()

    # Filter based on read status if needed
    if read_filter == "unread":
        contents = [c for c in contents if c.id not in read_content_ids]
    elif read_filter == "read":
        contents = [c for c in contents if c.id in read_content_ids]
    # If read_filter is "all", don't filter

    # Convert to domain objects and then to response format
    content_summaries = []
    for c in contents:
        try:
            domain_content = content_to_domain(c)

            # Get classification from metadata
            classification = None
            if domain_content.structured_summary:
                classification = domain_content.structured_summary.get("classification")

            content_summaries.append(
                ContentSummaryResponse(
                    id=domain_content.id,
                    content_type=domain_content.content_type.value,
                    url=str(domain_content.url),
                    title=domain_content.display_title,
                    source=domain_content.source,
                    status=domain_content.status.value,
                    short_summary=domain_content.short_summary,
                    created_at=domain_content.created_at.isoformat()
                    if domain_content.created_at
                    else "",
                    processed_at=domain_content.processed_at.isoformat()
                    if domain_content.processed_at
                    else None,
                    classification=classification,
                    publication_date=domain_content.publication_date.isoformat()
                    if domain_content.publication_date
                    else None,
                    is_read=c.id in read_content_ids,
                    is_favorited=c.id in favorite_content_ids,
                )
            )
        except Exception as e:
            # Skip content with invalid metadata
            print(f"Skipping content {c.id} due to validation error: {e}")
            continue

    # Get content types for filter
    content_types = [ct.value for ct in ContentType]

    return ContentListResponse(
        contents=content_summaries,
        total=len(content_summaries),
        available_dates=available_dates,
        content_types=content_types,
    )


@router.post(
    "/{content_id}/mark-read",
    summary="Mark content as read",
    description="Mark a specific content item as read.",
    responses={
        200: {"description": "Content marked as read successfully"},
        404: {"description": "Content not found"},
    },
)
async def mark_content_read(
    content_id: int = Path(..., description="Content ID", gt=0),
    db: Session = Depends(get_db_session),
) -> dict:
    """Mark content as read."""
    from app.services import read_status

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Mark as read
    result = read_status.mark_content_as_read(db, content_id)
    if result:
        return {"status": "success", "content_id": content_id}
    else:
        return {"status": "error", "message": "Failed to mark as read"}


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
async def get_content_detail(
    content_id: int = Path(..., description="Content ID", gt=0),
    db: Session = Depends(get_db_session),
) -> ContentDetailResponse:
    """Get detailed view of a specific content item."""
    from app.services import read_status, favorites

    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check if content is read
    is_read = read_status.is_content_read(db, content_id)
    
    # Check if content is favorited
    is_favorited = favorites.is_content_favorited(db, content_id)

    # Convert to domain object to validate metadata
    try:
        domain_content = content_to_domain(content)
    except Exception as e:
        # If domain conversion fails, raise HTTP exception
        raise HTTPException(
            status_code=500, detail=f"Failed to process content metadata: {str(e)}"
        ) from e

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
        is_read=is_read,
        is_favorited=is_favorited,
        # Additional properties from ContentData
        summary=domain_content.summary,
        short_summary=domain_content.short_summary,
        structured_summary=domain_content.structured_summary,
        bullet_points=domain_content.bullet_points,
        quotes=domain_content.quotes,
        topics=domain_content.topics,
        full_markdown=domain_content.full_markdown,
    )


@router.post(
    "/bulk-mark-read",
    summary="Bulk mark content as read",
    description="Mark multiple content items as read in a single request.",
    responses={
        200: {"description": "Content items marked as read successfully"},
        400: {"description": "Invalid content IDs provided"},
    },
)
async def bulk_mark_read(
    request: BulkMarkReadRequest,
    db: Session = Depends(get_db_session),
) -> dict:
    """Mark multiple content items as read."""
    from app.services import read_status

    # Validate that all content IDs exist
    existing_ids = db.query(Content.id).filter(Content.id.in_(request.content_ids)).all()
    existing_ids = {row[0] for row in existing_ids}

    invalid_ids = set(request.content_ids) - existing_ids
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"Invalid content IDs: {sorted(invalid_ids)}")

    # Mark all as read
    success_count = 0
    failed_ids = []

    for content_id in request.content_ids:
        result = read_status.mark_content_as_read(db, content_id)
        if result:
            success_count += 1
        else:
            failed_ids.append(content_id)

    return {
        "status": "success",
        "marked_count": success_count,
        "failed_ids": failed_ids,
        "total_requested": len(request.content_ids),
    }


@router.delete(
    "/{content_id}/mark-unread",
    summary="Mark content as unread",
    description="Remove the read status from a specific content item.",
    responses={
        200: {"description": "Content marked as unread successfully"},
        404: {"description": "Content not found"},
    },
)
async def mark_content_unread(
    content_id: int = Path(..., description="Content ID", gt=0),
    db: Session = Depends(get_db_session),
) -> dict:
    """Mark content as unread by removing its read status."""
    from sqlalchemy import delete

    from app.models.schema import ContentReadStatus

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Delete read status
    result = db.execute(delete(ContentReadStatus).where(ContentReadStatus.content_id == content_id))
    db.commit()

    return {
        "status": "success",
        "content_id": content_id,
        "removed_records": result.rowcount,
    }


@router.post(
    "/{content_id}/favorite",
    summary="Toggle favorite status",
    description="Toggle the favorite status of a specific content item.",
    responses={
        200: {"description": "Favorite status toggled successfully"},
        404: {"description": "Content not found"},
    },
)
async def toggle_favorite(
    content_id: int = Path(..., description="Content ID", gt=0),
    db: Session = Depends(get_db_session),
) -> dict:
    """Toggle favorite status for content."""
    from app.services import favorites

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Toggle favorite
    is_favorited, _ = favorites.toggle_favorite(db, content_id)
    return {
        "status": "success",
        "content_id": content_id,
        "is_favorited": is_favorited,
    }


@router.delete(
    "/{content_id}/unfavorite", 
    summary="Remove from favorites",
    description="Remove a specific content item from favorites.",
    responses={
        200: {"description": "Content removed from favorites successfully"},
        404: {"description": "Content not found"},
    },
)
async def unfavorite_content(
    content_id: int = Path(..., description="Content ID", gt=0),
    db: Session = Depends(get_db_session),
) -> dict:
    """Remove content from favorites."""
    from app.services import favorites

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Remove from favorites
    removed = favorites.remove_favorite(db, content_id)
    return {
        "status": "success" if removed else "not_found",
        "content_id": content_id,
        "message": "Removed from favorites" if removed else "Content was not favorited",
    }


@router.get(
    "/favorites/list",
    response_model=ContentListResponse,
    summary="Get favorited content",
    description="Retrieve all favorited content items.",
)
async def get_favorites(
    db: Session = Depends(get_db_session),
) -> ContentListResponse:
    """Get all favorited content."""
    from app.services import read_status, favorites

    # Get favorited content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db)
    
    # Get read content IDs
    read_content_ids = read_status.get_read_content_ids(db)

    # Query favorited content
    contents = db.query(Content).filter(Content.id.in_(favorite_content_ids)).order_by(Content.created_at.desc()).all() if favorite_content_ids else []

    # Convert to response format
    content_summaries = []
    for c in contents:
        try:
            domain_content = content_to_domain(c)

            # Get classification from metadata
            classification = None
            if domain_content.structured_summary:
                classification = domain_content.structured_summary.get("classification")

            content_summaries.append(
                ContentSummaryResponse(
                    id=domain_content.id,
                    content_type=domain_content.content_type.value,
                    url=str(domain_content.url),
                    title=domain_content.display_title,
                    source=domain_content.source,
                    status=domain_content.status.value,
                    short_summary=domain_content.short_summary,
                    created_at=domain_content.created_at.isoformat()
                    if domain_content.created_at
                    else "",
                    processed_at=domain_content.processed_at.isoformat()
                    if domain_content.processed_at
                    else None,
                    classification=classification,
                    publication_date=domain_content.publication_date.isoformat()
                    if domain_content.publication_date
                    else None,
                    is_read=c.id in read_content_ids,
                    is_favorited=True,  # All items in this list are favorited
                )
            )
        except Exception as e:
            print(f"Skipping content {c.id} due to validation error: {e}")
            continue

    # Get content types for filter
    content_types = [ct.value for ct in ContentType]

    return ContentListResponse(
        contents=content_summaries,
        total=len(content_summaries),
        available_dates=[],  # Not needed for favorites list
        content_types=content_types,
    )
