"""Content listing and search endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.core.timing import timed
from app.domain.converters import content_to_domain
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentStatusEntry
from app.models.user import User
from app.routers.api.models import ContentListResponse, ContentSummaryResponse, UnreadCountsResponse
from app.utils.pagination import PaginationCursor

router = APIRouter()


@router.get(
    "/",
    response_model=ContentListResponse,
    summary="List content items",
    description=(
        "Retrieve a list of content items with optional filtering by content type and date. "
        "Supports multiple content types via repeated query parameters "
        "(e.g., ?content_type=article&content_type=podcast). "
        "Supports cursor-based pagination for efficient loading."
    ),
)
async def list_contents(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    content_type: list[str] | None = Query(
        None,
        description=(
            "Filter by content type(s). Can be specified multiple times "
            "for multiple types (article/podcast/news)"
        ),
    ),
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
    from app.services import favorites, read_status

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
    with timed("get_read_content_ids"):
        read_content_ids = read_status.get_read_content_ids(db, current_user.id)

    # Get favorited content IDs
    with timed("get_favorite_content_ids"):
        favorite_content_ids = favorites.get_favorite_content_ids(db, current_user.id)

    inbox_exists = (
        db.query(ContentStatusEntry.id)
        .filter(
            ContentStatusEntry.content_id == Content.id,
            ContentStatusEntry.user_id == current_user.id,
            ContentStatusEntry.status == "inbox",
        )
        .exists()
    )

    # Visibility clause: include summarized content or completed news
    summarized_clause = Content.content_metadata["summary"].is_not(None) & (
        Content.content_metadata["summary"] != "null"
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
            .filter(or_(Content.content_type == ContentType.NEWS.value, inbox_exists))
            .distinct()
            .order_by(func.date(Content.created_at).desc())
        )

        with timed("query available_dates"):
            for row in available_dates_query.all():
                if row.date:
                    if isinstance(row.date, str):
                        available_dates.append(row.date)
                    else:
                        available_dates.append(row.date.strftime("%Y-%m-%d"))

    # Query content
    query = db.query(Content)
    query = query.filter(or_(Content.content_type == ContentType.NEWS.value, inbox_exists))

    # Filter out "skip" classification articles
    query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))

    # Only show content that has summary or is news (match HTML view)
    query = query.filter(or_(summarized_clause, completed_news_clause))

    # Apply content type filter - support multiple types
    if content_type:
        # Remove "all" from list if present and filter
        types = [t for t in content_type if t != "all"]
        if types:
            query = query.filter(Content.content_type.in_(types))

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
    with timed("query content_list"):
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
                    is_aggregate=is_aggregate,
                    item_count=item_count,
                    news_article_url=news_article_url,
                    news_discussion_url=news_discussion_url,
                    news_key_points=news_key_points,
                    news_summary=news_summary_text,
                    user_status="inbox"
                    if domain_content.content_type in (ContentType.ARTICLE, ContentType.PODCAST)
                    else None,
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
    current_user: Annotated[User, Depends(get_current_user)],
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
    from app.services import favorites, read_status

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
    with timed("search: get_read_content_ids"):
        read_content_ids = read_status.get_read_content_ids(db, current_user.id)
    with timed("search: get_favorite_content_ids"):
        favorite_content_ids = favorites.get_favorite_content_ids(db, current_user.id)

    inbox_exists = (
        db.query(ContentStatusEntry.id)
        .filter(
            ContentStatusEntry.content_id == Content.id,
            ContentStatusEntry.user_id == current_user.id,
            ContentStatusEntry.status == "inbox",
        )
        .exists()
    )

    # Base query aligning with list endpoint visibility rules
    query = db.query(Content)
    query = query.filter(or_(Content.content_type == ContentType.NEWS.value, inbox_exists))

    # Filter out "skip" classification articles
    query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))

    summarized_clause = Content.content_metadata["summary"].is_not(None) & (
        Content.content_metadata["summary"] != "null"
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
    with timed("query search_results"):
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
                    is_aggregate=domain_content.is_aggregate,
                    item_count=len(domain_content.news_items)
                    if domain_content.content_type == ContentType.NEWS
                    else None,
                    user_status="inbox"
                    if domain_content.content_type in (ContentType.ARTICLE, ContentType.PODCAST)
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


@router.get(
    "/unread-counts",
    response_model=UnreadCountsResponse,
    summary="Get unread content counts by type",
    description="Get the total count of unread items for each content type.",
)
async def get_unread_counts(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UnreadCountsResponse:
    """Get unread counts for each content type."""
    from app.services import read_status

    # Get read content IDs
    with timed("unread_counts: get_read_content_ids"):
        read_content_ids = read_status.get_read_content_ids(db, current_user.id)

    inbox_exists = (
        db.query(ContentStatusEntry.id)
        .filter(
            ContentStatusEntry.content_id == Content.id,
            ContentStatusEntry.user_id == current_user.id,
            ContentStatusEntry.status == "inbox",
        )
        .exists()
    )

    # Visibility clause: include summarized content or completed news
    summarized_clause = Content.content_metadata["summary"].is_not(None) & (
        Content.content_metadata["summary"] != "null"
    )
    completed_news_clause = and_(
        Content.content_type == ContentType.NEWS.value,
        Content.status == ContentStatus.COMPLETED.value,
    )

    # Base query for visible, non-skipped content
    base_query = (
        db.query(Content.id, Content.content_type)
        .filter(or_(summarized_clause, completed_news_clause))
        .filter(or_(Content.content_type == ContentType.NEWS.value, inbox_exists))
        .filter((Content.classification != "skip") | (Content.classification.is_(None)))
    )

    # Get all visible content
    with timed("query unread_counts"):
        all_content = base_query.all()

    # Count unread items by type
    counts = {"article": 0, "podcast": 0, "news": 0}
    for content_id, content_type in all_content:
        if content_id not in read_content_ids and content_type in counts:
            counts[content_type] += 1

    return UnreadCountsResponse(
        article=counts["article"], podcast=counts["podcast"], news=counts["news"]
    )
