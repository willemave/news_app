"""Content listing and search endpoints."""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, cast, func, or_
from sqlalchemy.orm import Session

from app.core.db import get_readonly_db_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.core.timing import timed
from app.models.metadata import ContentStatus, ContentType
from app.models.pagination import PaginationMetadata
from app.models.schema import Content, ContentFavorites, ContentReadStatus, ContentStatusEntry
from app.models.user import User
from app.presenters.content_presenter import (
    build_content_summary_response,
    build_domain_content,
    is_ready_for_list,
    resolve_image_urls,
)
from app.repositories.content_repository import (
    apply_sqlite_fts_filter,
    apply_visibility_filters,
    build_fts_match_query,
    build_visibility_context,
    sqlite_fts_available,
)
from app.routers.api.models import (
    ContentListResponse,
    ContentSummaryResponse,
    PodcastEpisodeSearchResponse,
    PodcastEpisodeSearchResultResponse,
)
from app.services.podcast_search import search_podcast_episodes
from app.utils.pagination import PaginationCursor

logger = get_logger(__name__)

AVAILABLE_DATES_LOOKBACK_DAYS = 120

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
def list_contents(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    content_type: Annotated[
        list[str] | None,
        Query(
            description=(
                "Filter by content type(s). Can be specified multiple times "
                "for multiple types (article/podcast/news)"
            ),
        ),
    ] = None,
    date: Annotated[
        str | None,
        Query(description="Filter by date (YYYY-MM-DD format)", pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    ] = None,
    read_filter: Annotated[
        str,
        Query(
            description="Filter by read status (all/read/unread)",
            pattern="^(all|read|unread)$",
        ),
    ] = "all",
    cursor: Annotated[str | None, Query(description="Pagination cursor for next page")] = None,
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=100,
            description="Number of items per page (max 100)",
        ),
    ] = 25,
) -> ContentListResponse:
    """List content with optional filters and cursor-based pagination."""
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
                    detail="Cursor invalid: filters changed. Start a new pagination.",
                )
            last_id = cursor_data["last_id"]
            last_created_at = cursor_data["last_created_at"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    context = build_visibility_context(current_user.id)

    # Get available dates for the dropdown (only on first page)
    # Optimized: Skip expensive JSON extraction since inbox items are always summarized
    # and news items are always completed before becoming visible
    available_dates = []
    if not cursor:
        lookback_start = datetime.now(UTC) - timedelta(days=AVAILABLE_DATES_LOOKBACK_DAYS)
        available_dates_query = db.query(func.date(Content.created_at).label("date")).filter(
            Content.created_at >= lookback_start
        )
        available_dates_query = (
            apply_visibility_filters(available_dates_query, context)
            .distinct()
            .order_by(func.date(Content.created_at).desc())
            .limit(90)
        )

        with timed("query available_dates"):
            for row in available_dates_query.all():
                if row.date:
                    if isinstance(row.date, str):
                        available_dates.append(row.date)
                    else:
                        available_dates.append(row.date.strftime("%Y-%m-%d"))

    # Base visible content query with user-scoped flags
    query = (
        db.query(
            Content,
            ContentReadStatus.id.label("is_read"),
            ContentFavorites.id.label("is_favorited"),
        )
        .outerjoin(
            ContentReadStatus,
            and_(
                ContentReadStatus.content_id == Content.id,
                ContentReadStatus.user_id == current_user.id,
            ),
        )
        .outerjoin(
            ContentFavorites,
            and_(
                ContentFavorites.content_id == Content.id,
                ContentFavorites.user_id == current_user.id,
            ),
        )
        .outerjoin(
            ContentStatusEntry,
            and_(
                ContentStatusEntry.content_id == Content.id,
                ContentStatusEntry.user_id == current_user.id,
                ContentStatusEntry.status == "inbox",
            ),
        )
    )
    query = query.filter(Content.status == ContentStatus.COMPLETED.value)
    query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))
    query = query.filter(ContentStatusEntry.id.is_not(None))

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
            start_dt = datetime.combine(filter_date, datetime.min.time())
            end_dt = start_dt + timedelta(days=1)
            query = query.filter(Content.created_at >= start_dt, Content.created_at < end_dt)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid date format") from e

    # Apply read status filter in SQL query
    if read_filter == "unread":
        query = query.filter(ContentReadStatus.id.is_(None))
    elif read_filter == "read":
        query = query.filter(ContentReadStatus.id.is_not(None))

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
        content_rows = query.limit(limit + 1).all()

    # Check if there are more results
    has_more = len(content_rows) > limit
    if has_more:
        content_rows = content_rows[:limit]  # Trim to requested limit

    # Convert to domain objects and then to response format
    content_summaries = []
    for row in content_rows:
        try:
            content, is_read, is_favorited = row
            domain_content = build_domain_content(content)

            image_url, thumbnail_url = resolve_image_urls(domain_content)
            if not is_ready_for_list(domain_content, image_url):
                continue

            content_summaries.append(
                build_content_summary_response(
                    content=content,
                    domain_content=domain_content,
                    is_read=bool(is_read),
                    is_favorited=bool(is_favorited),
                    image_url=image_url,
                    thumbnail_url=thumbnail_url,
                )
            )
        except Exception as e:
            # Skip content with invalid metadata
            logger.warning(
                "Skipping content %s due to validation error: %s",
                content.id,
                e,
                extra={
                    "component": "content_list",
                    "operation": "build_content_list",
                    "item_id": content.id,
                    "context_data": {"content_id": content.id},
                },
            )
            continue

    # Get content types for filter
    content_types = [ct.value for ct in ContentType]

    # Generate next cursor if there are more results
    next_cursor = None
    if has_more and content_rows:
        last_item = content_rows[-1][0]  # Use original DB object, not domain object
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
        available_dates=available_dates,
        content_types=content_types,
        meta=PaginationMetadata(
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=len(content_summaries),
            total=len(content_summaries),
        ),
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
def search_contents(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(
        ..., min_length=2, max_length=200, description="Search query (min 2 characters)"
    ),
    type: str = Query(
        "all",
        pattern=r"^(all|article|podcast|news)$",
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

    When available, this uses SQLite FTS5 for fast, indexed search over titles,
    sources, summaries, and transcripts. Otherwise it falls back to case-insensitive
    LIKE over title/source and selected JSON fields (summary.title/summary.overview/
    summary.hook) with a safe String cast for portability between SQLite and Postgres.
    As a fallback, the entire JSON is also matched as text to catch legacy structures.
    """
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
                    detail="Cursor invalid: search params changed. Start a new search.",
                )
            last_id = cursor_data["last_id"]
            last_created_at = cursor_data["last_created_at"]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    # Base query aligning with list endpoint visibility rules
    query = (
        db.query(
            Content,
            ContentReadStatus.id.label("is_read"),
            ContentFavorites.id.label("is_favorited"),
        )
        .outerjoin(
            ContentReadStatus,
            and_(
                ContentReadStatus.content_id == Content.id,
                ContentReadStatus.user_id == current_user.id,
            ),
        )
        .outerjoin(
            ContentFavorites,
            and_(
                ContentFavorites.content_id == Content.id,
                ContentFavorites.user_id == current_user.id,
            ),
        )
        .outerjoin(
            ContentStatusEntry,
            and_(
                ContentStatusEntry.content_id == Content.id,
                ContentStatusEntry.user_id == current_user.id,
                ContentStatusEntry.status == "inbox",
            ),
        )
    )
    query = query.filter(Content.status == ContentStatus.COMPLETED.value)
    query = query.filter((Content.classification != "skip") | (Content.classification.is_(None)))
    query = query.filter(
        or_(
            Content.content_type == ContentType.NEWS.value,
            ContentStatusEntry.id.is_not(None),
        )
    )

    if type and type != "all":
        query = query.filter(Content.content_type == type)

    match_query = build_fts_match_query(q)
    if match_query and sqlite_fts_available(db):
        search_query = apply_sqlite_fts_filter(query, match_query)
    else:
        search = f"%{q.lower()}%"

        # Build portable search OR-clause
        conditions = or_(
            func.lower(Content.title).like(search),
            func.lower(Content.source).like(search),
            # Prefer targeted JSON fields when present
            func.lower(cast(Content.content_metadata["summary"]["title"], String)).like(search),
            func.lower(cast(Content.content_metadata["summary"]["overview"], String)).like(search),
            func.lower(cast(Content.content_metadata["summary"]["hook"], String)).like(search),
            func.lower(cast(Content.content_metadata["summary"]["takeaway"], String)).like(search),
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

    content_summaries: list[ContentSummaryResponse] = []
    for c in results:
        try:
            content, is_read, is_favorited = c
            domain_content = build_domain_content(content)
            image_url, thumbnail_url = resolve_image_urls(domain_content)
            if not is_ready_for_list(domain_content, image_url):
                continue

            content_summaries.append(
                build_content_summary_response(
                    content=content,
                    domain_content=domain_content,
                    is_read=bool(is_read),
                    is_favorited=bool(is_favorited),
                    image_url=image_url,
                    thumbnail_url=thumbnail_url,
                )
            )
        except Exception as e:
            logger.warning(
                "Skipping content %s due to validation error: %s",
                content.id,
                e,
                extra={
                    "component": "content_list",
                    "operation": "search_content",
                    "item_id": content.id,
                    "context_data": {"content_id": content.id},
                },
            )
            continue

    total = len(content_summaries)  # Only count current page for performance

    # Generate next cursor if there are more results
    next_cursor = None
    if has_more and results:
        last_item = results[-1][0]  # Use original DB object
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
        available_dates=[],  # Not applicable for search
        content_types=[ct.value for ct in ContentType],
        meta=PaginationMetadata(
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=len(content_summaries),
            total=total,
        ),
    )


@router.get(
    "/search/podcasts",
    response_model=PodcastEpisodeSearchResponse,
    summary="Search for podcast episodes across the web",
    description=(
        "Search external podcast episode pages and return addable episode URLs. "
        "Uses the same online discovery search infrastructure with provider fallbacks."
    ),
)
def search_podcast_episode_matches(
    current_user: Annotated[User, Depends(get_current_user)],
    q: str = Query(
        ..., min_length=2, max_length=200, description="Podcast search query (min 2 characters)"
    ),
    limit: int = Query(10, ge=1, le=25, description="Max episode matches to return"),
) -> PodcastEpisodeSearchResponse:
    """Search external podcast episodes for direct add-to-inbox flows."""
    del current_user  # Require auth for parity with other content search endpoints.

    results = search_podcast_episodes(query=q, limit=limit)
    return PodcastEpisodeSearchResponse(
        results=[
            PodcastEpisodeSearchResultResponse(
                title=result.title,
                episode_url=result.episode_url,
                podcast_title=result.podcast_title,
                source=result.source,
                snippet=result.snippet,
                feed_url=result.feed_url,
                published_at=result.published_at,
                provider=result.provider,
                score=result.score,
            )
            for result in results
        ]
    )
