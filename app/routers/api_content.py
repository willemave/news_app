"""API endpoints for content with OpenAPI documentation."""

from datetime import datetime
from typing import Annotated, Any
from urllib.parse import quote_plus

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.domain.converters import content_to_domain
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.utils.pagination import PaginationCursor

router = APIRouter(
    tags=["content"],
    responses={404: {"description": "Not found"}},
)


# Response models for OpenAPI
class ContentSummaryResponse(BaseModel):
    """Summary information for a content item in list view."""

    id: int = Field(..., description="Unique identifier")
    content_type: str = Field(..., description="Type of content (article/podcast/news)")
    url: str = Field(..., description="Original URL of the content")
    title: str | None = Field(None, description="Content title")
    source: str | None = Field(
        None, description="Content source (e.g., substack name, podcast name)"
    )
    platform: str | None = Field(
        None, description="Content platform (e.g., twitter, substack, youtube)"
    )
    status: str = Field(..., description="Processing status")
    short_summary: str | None = Field(
        None,
        description=(
            "Short summary for display; for news items this returns the excerpt or first item text"
        ),
    )
    created_at: str = Field(..., description="ISO timestamp when content was created")
    processed_at: str | None = Field(None, description="ISO timestamp when content was processed")
    classification: str | None = Field(None, description="Content classification (to_read/skip)")
    publication_date: str | None = Field(
        None, description="ISO timestamp of when content was published"
    )
    is_read: bool = Field(False, description="Whether the content has been marked as read")
    is_favorited: bool = Field(False, description="Whether the content has been favorited")
    is_unliked: bool = Field(False, description="Whether the content has been unliked")
    is_aggregate: bool = Field(
        False, description="Whether this news item aggregates multiple links"
    )
    item_count: int | None = Field(
        None, description="Number of child items when content_type is news"
    )
    news_article_url: str | None = Field(
        None, description="Canonical article link for news content"
    )
    news_discussion_url: str | None = Field(
        None, description="Aggregator discussion URL (HN thread, tweet, etc.)"
    )
    news_key_points: list[str] | None = Field(
        None, description="Key points provided for news digests"
    )
    news_summary: str | None = Field(
        None, description="Short overview synthesized for news digests"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "content_type": "article",
                "url": "https://example.com/article",
                "title": "Understanding AI in 2025",
                "source": "Tech Blog",
                "platform": "substack",
                "status": "completed",
                "short_summary": "This article explores the latest developments in AI...",
                "created_at": "2025-06-19T10:30:00Z",
                "processed_at": "2025-06-19T10:35:00Z",
                "classification": "to_read",
                "publication_date": "2025-06-18T12:00:00Z",
                "is_read": False,
                "is_aggregate": False,
                "item_count": None,
            }
        }


class ContentListResponse(BaseModel):
    """Response for content list endpoint."""

    contents: list[ContentSummaryResponse] = Field(..., description="List of content items")
    total: int = Field(..., description="Total number of items")
    available_dates: list[str] = Field(..., description="List of available dates (YYYY-MM-DD)")
    content_types: list[str] = Field(..., description="Available content types for filtering")
    next_cursor: str | None = Field(
        None, description="Opaque cursor token for next page (null if no more results)"
    )
    has_more: bool = Field(False, description="Whether more results are available")
    page_size: int = Field(0, description="Number of items in current response")

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
                        "platform": "substack",
                        "status": "completed",
                        "short_summary": "This article explores...",
                        "created_at": "2025-06-19T10:30:00Z",
                        "processed_at": "2025-06-19T10:35:00Z",
                        "classification": "to_read",
                    }
                ],
                "total": 1,
                "available_dates": ["2025-06-19", "2025-06-18"],
                "content_types": ["article", "podcast", "news"],
                "next_cursor": "eyJsYXN0X2lkIjoxMjMsImxhc3RfY3JlYXRlZF9hdCI6IjIwMjUtMDYtMTlUMTA6MzA6MDAifQ==",
                "has_more": True,
                "page_size": 25,
            }
        }


class ContentDetailResponse(BaseModel):
    """Detailed response for a single content item."""

    id: int = Field(..., description="Unique identifier")
    content_type: str = Field(..., description="Type of content (article/podcast/news)")
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
    is_unliked: bool = Field(False, description="Whether the content has been unliked")
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
    is_aggregate: bool = Field(False, description="Whether this content aggregates multiple items")
    rendered_markdown: str | None = Field(
        None, description="Rendered markdown list for legacy news aggregates"
    )
    news_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Legacy structured child items for news content",
    )
    news_article_url: str | None = Field(
        None, description="Canonical article link for news content"
    )
    news_discussion_url: str | None = Field(
        None, description="Aggregator discussion URL (HN thread, tweet, etc.)"
    )
    news_key_points: list[str] | None = Field(
        None, description="Key points provided for news digests"
    )
    news_summary: str | None = Field(
        None, description="Short overview synthesized for news digests"
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
                "is_aggregate": False,
                "rendered_markdown": None,
                "news_items": [],
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


class ChatGPTUrlResponse(BaseModel):
    """Response containing the ChatGPT URL for chatting with content."""

    chat_url: str = Field(..., description="URL to open ChatGPT with the content")
    truncated: bool = Field(..., description="Whether the content was truncated to fit URL limits")
    
    class Config:
        json_schema_extra = {
            "example": {
                "chat_url": "https://chat.openai.com/?q=Chat+about+this+article...",
                "truncated": False
            }
        }


@router.get(
    "/",
    response_model=ContentListResponse,
    summary="List content items",
    description=(
        "Retrieve a list of content items with optional filtering by content type and date. "
        "Supports cursor-based pagination for efficient loading."
    ),
)
async def list_contents(
    db: Annotated[Session, Depends(get_db_session)],
    content_type: str | None = Query(None, description="Filter by content type (article/podcast/news)"),
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
    cursor: str | None = Query(None, description="Pagination cursor for next page"),
    limit: int = Query(
        25,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
    ),
) -> ContentListResponse:
    """List content with optional filters and cursor-based pagination."""
    from app.services import favorites, read_status, unlikes

    # Decode cursor if provided
    last_id = None
    last_created_at = None
    if cursor:
        try:
            cursor_data = PaginationCursor.decode_cursor(cursor)
            # Validate cursor filters match current request
            current_filters = {
                "content_type": content_type,
                "date": date,
                "read_filter": read_filter,
            }
            if not PaginationCursor.validate_cursor(cursor_data, current_filters):
                raise HTTPException(
                    status_code=400,
                    detail="Cursor invalid: filters have changed. Please start a new pagination sequence.",
                )
            last_id = cursor_data["last_id"]
            last_created_at = cursor_data["last_created_at"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # Get read content IDs first
    read_content_ids = read_status.get_read_content_ids(db)

    # Get favorited content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db)

    # Get unliked content IDs
    unliked_content_ids = unlikes.get_unliked_content_ids(db)

    # Visibility clause: include summarized content or completed news
    summarized_clause = (
        Content.content_metadata["summary"].is_not(None)
        & (Content.content_metadata["summary"] != "null")
    )
    completed_news_clause = and_(
        Content.content_type == ContentType.NEWS.value,
        Content.status == ContentStatus.COMPLETED.value,
    )

    # Get available dates for the dropdown (only on first page)
    available_dates = []
    if not cursor:
        available_dates_query = (
            db.query(func.date(Content.created_at).label("date"))
            .filter(or_(summarized_clause, completed_news_clause))
            .filter((Content.classification != "skip") | (Content.classification.is_(None)))
            .distinct()
            .order_by(func.date(Content.created_at).desc())
        )

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

    # Only show content that has summary or is news (match HTML view)
    query = query.filter(or_(summarized_clause, completed_news_clause))

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

    # Apply read status filter in SQL query
    if read_filter == "unread":
        query = query.filter(~Content.id.in_(read_content_ids))
    elif read_filter == "read":
        query = query.filter(Content.id.in_(read_content_ids))
    # If read_filter is "all", don't filter

    # Apply cursor pagination
    if last_id and last_created_at:
        # Use keyset pagination: WHERE (created_at, id) < (last_created_at, last_id)
        query = query.filter(
            or_(
                Content.created_at < last_created_at,
                and_(Content.created_at == last_created_at, Content.id < last_id),
            )
        )

    # Order by created_at DESC, id DESC for stable pagination
    query = query.order_by(Content.created_at.desc(), Content.id.desc())

    # Fetch limit + 1 to determine if there are more results
    contents = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(contents) > limit
    if has_more:
        contents = contents[:limit]  # Trim to requested limit

    # Convert to domain objects and then to response format
    content_summaries = []
    for c in contents:
        try:
            domain_content = content_to_domain(c)

            # Get classification from metadata
            classification = None
            if domain_content.structured_summary:
                classification = domain_content.structured_summary.get("classification")

            news_article_url = None
            news_discussion_url = None
            news_key_points = None
            news_summary_text = domain_content.short_summary
            item_count = None
            is_aggregate = domain_content.is_aggregate

            if domain_content.content_type == ContentType.NEWS:
                article_meta = (domain_content.metadata or {}).get("article", {})
                aggregator_meta = (domain_content.metadata or {}).get("aggregator", {})
                summary_meta = (domain_content.metadata or {}).get("summary", {})
                key_points = summary_meta.get("bullet_points")

                news_article_url = article_meta.get("url")
                news_discussion_url = aggregator_meta.get("url")
                if key_points:
                    news_key_points = [
                        point["text"] if isinstance(point, dict) else point for point in key_points
                    ]
                classification = summary_meta.get("classification") or classification
                news_summary_text = summary_meta.get("overview") or domain_content.summary
                is_aggregate = False

            content_summaries.append(
                ContentSummaryResponse(
                    id=domain_content.id,
                    content_type=domain_content.content_type.value,
                    url=str(domain_content.url),
                    title=domain_content.display_title,
                    source=domain_content.source,
                    platform=domain_content.platform or c.platform,
                    status=domain_content.status.value,
                    short_summary=news_summary_text,
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
                    is_unliked=c.id in unliked_content_ids,
                    is_aggregate=is_aggregate,
                    item_count=item_count,
                    news_article_url=news_article_url,
                    news_discussion_url=news_discussion_url,
                    news_key_points=news_key_points,
                    news_summary=news_summary_text,
                )
            )
        except Exception as e:
            # Skip content with invalid metadata
            print(f"Skipping content {c.id} due to validation error: {e}")
            continue

    # Get content types for filter
    content_types = [ct.value for ct in ContentType]

    # Generate next cursor if there are more results
    next_cursor = None
    if has_more and content_summaries:
        last_item = contents[-1]  # Use original DB object, not domain object
        current_filters = {
            "content_type": content_type,
            "date": date,
            "read_filter": read_filter,
        }
        next_cursor = PaginationCursor.encode_cursor(
            last_id=last_item.id,
            last_created_at=last_item.created_at,
            filters=current_filters,
        )

    return ContentListResponse(
        contents=content_summaries,
        total=len(content_summaries),
        available_dates=available_dates,
        content_types=content_types,
        next_cursor=next_cursor,
        has_more=has_more,
        page_size=len(content_summaries),
    )
 
@router.get(
    "/search",
    response_model=ContentListResponse,
    summary="Search content across articles and podcasts",
    description=(
        "Case-insensitive string search across titles, sources, and summaries. "
        "Results exclude items classified as 'skip' and only include summarized content. "
        "Supports cursor-based pagination for efficient loading."
    ),
)
async def search_contents(
    db: Annotated[Session, Depends(get_db_session)],
    q: str = Query(
        ..., min_length=2, max_length=200, description="Search query (min 2 characters)"
    ),
    type: str = Query(
        "all",
        regex=r"^(all|article|podcast|news)$",
        description="Optional content type filter",
    ),
    limit: int = Query(25, ge=1, le=100, description="Max results to return"),
    cursor: str | None = Query(None, description="Pagination cursor for next page"),
    offset: int = Query(
        0,
        ge=0,
        description="Results offset for pagination (deprecated, use cursor instead)",
        deprecated=True,
    ),
) -> ContentListResponse:
    """Search content with portable SQL patterns and cursor-based pagination.

    This uses case-insensitive LIKE over title/source and selected JSON fields
    (summary.title/summary.overview) with a safe String cast for portability
    between SQLite and Postgres. As a fallback, the entire JSON is also matched
    as text to catch legacy structures.
    """
    from app.services import favorites, read_status, unlikes

    # Decode cursor if provided (takes precedence over offset)
    last_id = None
    last_created_at = None
    if cursor:
        try:
            cursor_data = PaginationCursor.decode_cursor(cursor)
            # Validate cursor filters match current request
            current_filters = {
                "q": q,
                "type": type,
            }
            if not PaginationCursor.validate_cursor(cursor_data, current_filters):
                raise HTTPException(
                    status_code=400,
                    detail="Cursor invalid: search parameters have changed. Please start a new search.",
                )
            last_id = cursor_data["last_id"]
            last_created_at = cursor_data["last_created_at"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # Preload state flags
    read_content_ids = read_status.get_read_content_ids(db)
    favorite_content_ids = favorites.get_favorite_content_ids(db)
    unliked_content_ids = unlikes.get_unliked_content_ids(db)

    # Base query aligning with list endpoint visibility rules
    query = db.query(Content)

    # Filter out "skip" classification articles
    query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))

    summarized_clause = (
        Content.content_metadata["summary"].is_not(None)
        & (Content.content_metadata["summary"] != "null")
    )
    completed_news_clause = and_(
        Content.content_type == ContentType.NEWS.value,
        Content.status == ContentStatus.COMPLETED.value,
    )
    query = query.filter(or_(summarized_clause, completed_news_clause))

    if type and type != "all":
        query = query.filter(Content.content_type == type)

    search = f"%{q.lower()}%"

    # Build portable search OR-clause
    conditions = or_(
        func.lower(Content.title).like(search),
        func.lower(Content.source).like(search),
        # Prefer targeted JSON fields when present
        func.lower(cast(Content.content_metadata["summary"]["title"], String)).like(search),
        func.lower(cast(Content.content_metadata["summary"]["overview"], String)).like(search),
        # Podcasts may have transcript text in metadata
        func.lower(cast(Content.content_metadata["transcript"], String)).like(search),
        # Fallback: scan entire JSON blob as text (portable, but slower)
        func.lower(cast(Content.content_metadata, String)).like(search),
    )

    search_query = query.filter(conditions)

    # Order by created_at DESC, id DESC for stable pagination (must be before offset/limit)
    search_query = search_query.order_by(Content.created_at.desc(), Content.id.desc())

    # Apply cursor pagination if cursor is provided, otherwise use offset (deprecated)
    if cursor and last_id and last_created_at:
        search_query = search_query.filter(
            or_(
                Content.created_at < last_created_at,
                and_(Content.created_at == last_created_at, Content.id < last_id),
            )
        )
    elif not cursor and offset > 0:
        # Use offset only if no cursor provided (backwards compatibility)
        search_query = search_query.offset(offset)

    # Fetch limit + 1 to determine if there are more results
    results = search_query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(results) > limit
    if has_more:
        results = results[:limit]  # Trim to requested limit

    total = len(results)  # Only count current page for performance

    content_summaries: list[ContentSummaryResponse] = []
    for c in results:
        try:
            domain_content = content_to_domain(c)
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
                    platform=domain_content.platform or c.platform,
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
                    is_unliked=c.id in unliked_content_ids,
                    is_aggregate=domain_content.is_aggregate,
                    item_count=len(domain_content.news_items)
                    if domain_content.content_type == ContentType.NEWS
                    else None,
                )
            )
        except Exception as e:
            print(f"Skipping content {c.id} due to validation error: {e}")
            continue

    # Generate next cursor if there are more results
    next_cursor = None
    if has_more and content_summaries:
        last_item = results[-1]  # Use original DB object
        current_filters = {
            "q": q,
            "type": type,
        }
        next_cursor = PaginationCursor.encode_cursor(
            last_id=last_item.id,
            last_created_at=last_item.created_at,
            filters=current_filters,
        )

    return ContentListResponse(
        contents=content_summaries,
        total=total,
        available_dates=[],  # Not applicable for search
        content_types=[ct.value for ct in ContentType],
        next_cursor=next_cursor,
        has_more=has_more,
        page_size=len(content_summaries),
    )


class UnreadCountsResponse(BaseModel):
    """Response containing unread counts by content type."""

    article: int = Field(..., description="Number of unread articles")
    podcast: int = Field(..., description="Number of unread podcasts")
    news: int = Field(..., description="Number of unread news items")


@router.get(
    "/unread-counts",
    response_model=UnreadCountsResponse,
    summary="Get unread content counts by type",
    description="Get the total count of unread items for each content type.",
)
async def get_unread_counts(
    db: Annotated[Session, Depends(get_db_session)],
) -> UnreadCountsResponse:
    """Get unread counts for each content type."""
    from app.services import read_status

    # Get read content IDs
    read_content_ids = read_status.get_read_content_ids(db)

    # Visibility clause: include summarized content or completed news
    summarized_clause = (
        Content.content_metadata["summary"].is_not(None)
        & (Content.content_metadata["summary"] != "null")
    )
    completed_news_clause = and_(
        Content.content_type == ContentType.NEWS.value,
        Content.status == ContentStatus.COMPLETED.value,
    )

    # Base query for visible, non-skipped content
    base_query = (
        db.query(Content.id, Content.content_type)
        .filter(or_(summarized_clause, completed_news_clause))
        .filter((Content.classification != "skip") | (Content.classification.is_(None)))
    )

    # Get all visible content
    all_content = base_query.all()

    # Count unread items by type
    counts = {"article": 0, "podcast": 0, "news": 0}
    for content_id, content_type in all_content:
        if content_id not in read_content_ids:
            if content_type in counts:
                counts[content_type] += 1

    return UnreadCountsResponse(
        article=counts["article"],
        podcast=counts["podcast"],
        news=counts["news"]
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
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
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
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ContentDetailResponse:
    """Get detailed view of a specific content item."""
    from app.services import favorites, read_status, unlikes

    content = db.query(Content).filter(Content.id == content_id).first()

    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Check if content is read
    is_read = read_status.is_content_read(db, content_id)
    
    # Check if content is favorited
    is_favorited = favorites.is_content_favorited(db, content_id)
    # Check if content is unliked
    is_unliked = unlikes.is_content_unliked(db, content_id)

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
        news_summary_text = summary_meta.get("overview") or domain_content.summary
        structured_summary = None
        bullet_points = []
        quotes = []
        topics = []
        full_markdown = None
        rendered_markdown = None
        news_items = []

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
        is_unliked=is_unliked,
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
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """Mark multiple content items as read."""
    from app.services import read_status

    # Validate that all content IDs exist
    existing_ids = db.query(Content.id).filter(Content.id.in_(request.content_ids)).all()
    existing_ids = {row[0] for row in existing_ids}

    invalid_ids = set(request.content_ids) - existing_ids
    if invalid_ids:
        raise HTTPException(status_code=400, detail=f"Invalid content IDs: {sorted(invalid_ids)}")

    success_count, failed_ids = read_status.mark_contents_as_read(
        db,
        request.content_ids,
    )

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
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
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
    "/{content_id}/unlike",
    summary="Toggle unlike status",
    description="Toggle the unlike status of a specific content item. Also marks the item as read when unliked.",
    responses={
        200: {"description": "Unlike status toggled successfully"},
        404: {"description": "Content not found"},
    },
)
async def toggle_unlike(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """Toggle unlike status for content and mark as read when unliked."""
    from app.services import read_status, unlikes

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Toggle unlike
    is_unliked, _ = unlikes.toggle_unlike(db, content_id)

    # If now unliked, mark as read
    is_read = False
    if is_unliked:
        is_read = read_status.mark_content_as_read(db, content_id) is not None

    return {
        "status": "success",
        "content_id": content_id,
        "is_unliked": is_unliked,
        "is_read": is_read,
    }


@router.delete(
    "/{content_id}/remove-unlike",
    summary="Remove unlike",
    description="Remove the unlike status for a specific content item.",
    responses={
        200: {"description": "Content removed from unlikes successfully"},
        404: {"description": "Content not found"},
    },
)
async def remove_unlike_content(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict:
    """Remove content from unlikes."""
    from app.services import unlikes

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Remove from unlikes
    removed = unlikes.remove_unlike(db, content_id)
    return {
        "status": "success" if removed else "not_found",
        "content_id": content_id,
        "message": "Removed unlike" if removed else "Content was not unliked",
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
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
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
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
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
    description="Retrieve all favorited content items with cursor-based pagination.",
)
async def get_favorites(
    db: Annotated[Session, Depends(get_db_session)],
    cursor: str | None = Query(None, description="Pagination cursor for next page"),
    limit: int = Query(
        25,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
    ),
) -> ContentListResponse:
    """Get all favorited content with cursor-based pagination."""
    from app.services import favorites, read_status

    # Decode cursor if provided
    last_id = None
    last_created_at = None
    if cursor:
        try:
            cursor_data = PaginationCursor.decode_cursor(cursor)
            # No filter validation needed for favorites (no filters)
            last_id = cursor_data["last_id"]
            last_created_at = cursor_data["last_created_at"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # Get favorited content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db)

    # Get read content IDs
    read_content_ids = read_status.get_read_content_ids(db)

    # Query favorited content
    if favorite_content_ids:
        query = db.query(Content).filter(Content.id.in_(favorite_content_ids))

        # Filter out "skip" classification articles
        query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))

        # Apply cursor pagination
        if last_id and last_created_at:
            query = query.filter(
                or_(
                    Content.created_at < last_created_at,
                    and_(Content.created_at == last_created_at, Content.id < last_id),
                )
            )

        # Order by created_at DESC, id DESC for stable pagination
        query = query.order_by(Content.created_at.desc(), Content.id.desc())

        # Fetch limit + 1 to determine if there are more results
        contents = query.limit(limit + 1).all()

        # Check if there are more results
        has_more = len(contents) > limit
        if has_more:
            contents = contents[:limit]  # Trim to requested limit
    else:
        contents = []
        has_more = False

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
                    is_unliked=False,
                )
            )
        except Exception as e:
            print(f"Skipping content {c.id} due to validation error: {e}")
            continue

    # Get content types for filter
    content_types = [ct.value for ct in ContentType]

    # Generate next cursor if there are more results
    next_cursor = None
    if has_more and content_summaries:
        last_item = contents[-1]  # Use original DB object
        next_cursor = PaginationCursor.encode_cursor(
            last_id=last_item.id,
            last_created_at=last_item.created_at,
            filters={},  # No filters for favorites
        )

    return ContentListResponse(
        contents=content_summaries,
        total=len(content_summaries),
        available_dates=[],  # Not needed for favorites list
        content_types=content_types,
        next_cursor=next_cursor,
        has_more=has_more,
        page_size=len(content_summaries),
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
async def get_chatgpt_url(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
) -> ChatGPTUrlResponse:
    """Generate ChatGPT URL for chatting about the content."""
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
            truncated_content = content_text[:remaining_space // 3]  # Rough estimate for encoding
            truncated_prompt = context_part + "\n" + truncated_content + "\n\n[Content truncated for URL length...]"
        else:
            # Even context is too long, just use title and basic info
            truncated_prompt = f"Chat about: {domain_content.display_title}"
            if domain_content.source:
                truncated_prompt += f" from {domain_content.source}"

        encoded_prompt = quote_plus(truncated_prompt)
        full_url = base_url + encoded_prompt

    return ChatGPTUrlResponse(
        chat_url=full_url,
        truncated=truncated
    )


@router.get(
    "/recently-read/list",
    response_model=ContentListResponse,
    summary="Get recently read content",
    description=(
        "Retrieve all read content items sorted by read time "
        "(most recent first) with cursor-based pagination."
    ),
)
async def get_recently_read(
    db: Annotated[Session, Depends(get_db_session)],
    cursor: str | None = Query(None, description="Pagination cursor for next page"),
    limit: int = Query(
        25,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
    ),
) -> ContentListResponse:
    """Get all recently read content with cursor-based pagination, sorted by read time."""
    from app.models.schema import ContentReadStatus
    from app.services import favorites, read_status, unlikes

    # Decode cursor if provided
    last_id = None
    last_read_at = None
    if cursor:
        try:
            cursor_data = PaginationCursor.decode_cursor(cursor)
            last_id = cursor_data["last_id"]
            last_read_at = cursor_data.get("last_read_at")
            if last_read_at:
                last_read_at = datetime.fromisoformat(last_read_at)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # Get read content IDs for status checks
    read_content_ids = read_status.get_read_content_ids(db)

    # Get favorited content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db)

    # Get unliked content IDs
    unliked_content_ids = unlikes.get_unliked_content_ids(db)

    # Query content joined with read status, ordered by read time
    query = (
        db.query(Content, ContentReadStatus.read_at)
        .join(ContentReadStatus, Content.id == ContentReadStatus.content_id)
    )

    # Apply same visibility filters as other endpoints
    summarized_clause = (
        Content.content_metadata["summary"].is_not(None)
        & (Content.content_metadata["summary"] != "null")
    )
    completed_news_clause = and_(
        Content.content_type == ContentType.NEWS.value,
        Content.status == ContentStatus.COMPLETED.value,
    )
    query = query.filter(or_(summarized_clause, completed_news_clause))

    # Filter out "skip" classification articles
    query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))

    # Apply cursor pagination if provided
    if last_id and last_read_at:
        # Use keyset pagination: WHERE (read_at, content_id) < (last_read_at, last_id)
        query = query.filter(
            or_(
                ContentReadStatus.read_at < last_read_at,
                and_(ContentReadStatus.read_at == last_read_at, Content.id < last_id),
            )
        )

    # Order by read_at DESC, id DESC for stable pagination (most recently read first)
    query = query.order_by(ContentReadStatus.read_at.desc(), Content.id.desc())

    # Fetch limit + 1 to determine if there are more results
    results = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(results) > limit
    if has_more:
        results = results[:limit]  # Trim to requested limit

    # Extract content and read_at from results
    contents = []
    for c, read_at in results:
        contents.append((c, read_at))

    # Convert to response format
    content_summaries = []
    for c, _read_at in contents:
        try:
            domain_content = content_to_domain(c)

            # Get classification from metadata
            classification = None
            if domain_content.structured_summary:
                classification = domain_content.structured_summary.get("classification")

            news_article_url = None
            news_discussion_url = None
            news_key_points = None
            news_summary_text = domain_content.short_summary
            item_count = None
            is_aggregate = domain_content.is_aggregate

            if domain_content.content_type == ContentType.NEWS:
                article_meta = (domain_content.metadata or {}).get("article", {})
                aggregator_meta = (domain_content.metadata or {}).get("aggregator", {})
                summary_meta = (domain_content.metadata or {}).get("summary", {})
                key_points = summary_meta.get("bullet_points")

                news_article_url = article_meta.get("url")
                news_discussion_url = aggregator_meta.get("url")
                if key_points:
                    news_key_points = [
                        point["text"] if isinstance(point, dict) else point for point in key_points
                    ]
                classification = summary_meta.get("classification") or classification
                news_summary_text = summary_meta.get("overview") or domain_content.summary
                is_aggregate = False

            content_summaries.append(
                ContentSummaryResponse(
                    id=domain_content.id,
                    content_type=domain_content.content_type.value,
                    url=str(domain_content.url),
                    title=domain_content.display_title,
                    source=domain_content.source,
                    platform=domain_content.platform or c.platform,
                    status=domain_content.status.value,
                    short_summary=news_summary_text,
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
                    is_unliked=c.id in unliked_content_ids,
                    is_aggregate=is_aggregate,
                    item_count=item_count,
                    news_article_url=news_article_url,
                    news_discussion_url=news_discussion_url,
                    news_key_points=news_key_points,
                    news_summary=news_summary_text,
                )
            )
        except Exception as e:
            # Skip content with invalid metadata
            print(f"Skipping content {c.id} due to validation error: {e}")
            continue

    # Get content types for filter
    content_types = [ct.value for ct in ContentType]

    # Generate next cursor if there are more results
    next_cursor = None
    if has_more and content_summaries:
        last_item_content, last_item_read_at = contents[-1]
        next_cursor = PaginationCursor.encode_cursor(
            last_id=last_item_content.id,
            last_created_at=last_item_content.created_at,
            filters={"last_read_at": last_item_read_at.isoformat()},
        )

    return ContentListResponse(
        contents=content_summaries,
        total=len(content_summaries),
        available_dates=[],  # Not needed for recently read list
        content_types=content_types,
        next_cursor=next_cursor,
        has_more=has_more,
        page_size=len(content_summaries),
    )


class ConvertNewsResponse(BaseModel):
    """Response for converting news link to article."""

    status: str = Field(..., description="Operation status")
    new_content_id: int = Field(..., description="ID of the article content")
    original_content_id: int = Field(..., description="ID of the original news content")
    already_exists: bool = Field(..., description="Whether article already existed")
    message: str = Field(..., description="Human-readable message")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "new_content_id": 123,
                "original_content_id": 456,
                "already_exists": False,
                "message": "Article created and queued for processing"
            }
        }


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
            status_code=400,
            detail="Only news content can be converted to articles"
        )

    # Extract article URL from metadata
    metadata = content.content_metadata or {}
    article_meta = metadata.get("article", {})
    article_url = article_meta.get("url")

    if not article_url:
        raise HTTPException(
            status_code=400,
            detail="No article URL found in news metadata"
        )

    # Check if article already exists
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
            message="Article already exists in system"
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
    db.commit()
    db.refresh(new_article)

    return ConvertNewsResponse(
        status="success",
        new_content_id=new_article.id,
        original_content_id=content_id,
        already_exists=False,
        message="Article created and queued for processing"
    )

