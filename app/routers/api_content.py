"""API endpoints for content with OpenAPI documentation."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.converters import content_to_domain
from app.models.metadata import ContentData, ContentStatus, ContentType
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
            }
        }


@router.get(
    "/",
    response_model=ContentListResponse,
    summary="List content items",
    description="Retrieve a list of content items with optional filtering by content type and date.",
)
async def list_contents(
    content_type: str | None = Query(None, description="Filter by content type (article/podcast)"),
    date: str | None = Query(
        None,
        description="Filter by date (YYYY-MM-DD format)",
        regex="^\\d{4}-\\d{2}-\\d{2}$",
    ),
    db: Session = Depends(get_db_session),
) -> ContentListResponse:
    """List content with optional filters."""
    # Get available dates for the dropdown
    available_dates_query = (
        db.query(func.date(Content.created_at).label("date"))
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
    query = query.filter((Content.classification != "skip") | (Content.classification == None))

    # Apply content type filter
    if content_type and content_type != "all":
        query = query.filter(Content.content_type == content_type)

    # Apply date filter
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(func.date(Content.created_at) == filter_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format")

    # Order by most recent first
    contents = query.order_by(Content.created_at.desc()).all()

    # Convert to domain objects and then to response format
    content_summaries = []
    for c in contents:
        try:
            domain_content = content_to_domain(c)

            # Get classification from metadata
            classification = None
            if domain_content.metadata and "summary" in domain_content.metadata:
                summary_data = domain_content.metadata["summary"]
                if isinstance(summary_data, dict):
                    classification = summary_data.get("classification")

            content_summaries.append(
                ContentSummaryResponse(
                    id=domain_content.id,
                    content_type=domain_content.content_type.value,
                    url=str(domain_content.url),
                    title=domain_content.title,
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
    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Convert to domain object to validate metadata
    try:
        domain_content = content_to_domain(content)
    except Exception as e:
        # If domain conversion fails, return raw data
        return ContentDetailResponse(
            id=content.id,
            content_type=content.content_type,
            url=content.url,
            title=content.title,
            source=content.source,
            status=content.status,
            error_message=content.error_message,
            retry_count=content.retry_count or 0,
            metadata=content.content_metadata or {},
            created_at=content.created_at.isoformat() if content.created_at else "",
            updated_at=content.updated_at.isoformat() if content.updated_at else None,
            processed_at=content.processed_at.isoformat() if content.processed_at else None,
            checked_out_by=content.checked_out_by,
            checked_out_at=content.checked_out_at.isoformat() if content.checked_out_at else None,
        )

    # Return the validated content
    return ContentDetailResponse(
        id=domain_content.id,
        content_type=domain_content.content_type.value,
        url=str(domain_content.url),
        title=domain_content.title,
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
    )
