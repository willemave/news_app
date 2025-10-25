"""Read status management endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, delete, or_
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import get_current_user
from app.domain.converters import content_to_domain
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentReadStatus
from app.models.user import User
from app.routers.api.models import BulkMarkReadRequest, ContentListResponse, ContentSummaryResponse
from app.utils.pagination import PaginationCursor

router = APIRouter()


@router.post(
    "/{content_id}/mark-read",
    summary="Mark content as read",
    description="Mark a specific content item as read.",
    responses={
        200: {"description": "Content marked as read successfully"},
        404: {"description": "Content not found"},
        401: {"description": "Authentication required"},
    },
)
async def mark_content_read(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Mark content as read."""
    from app.services import read_status

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Mark as read
    result = read_status.mark_content_as_read(db, content_id, current_user.id)
    if result:
        return {"status": "success", "content_id": content_id}
    else:
        return {"status": "error", "message": "Failed to mark as read"}


@router.delete(
    "/{content_id}/mark-unread",
    summary="Mark content as unread",
    description="Remove the read status from a specific content item.",
    responses={
        200: {"description": "Content marked as unread successfully"},
        404: {"description": "Content not found"},
        401: {"description": "Authentication required"},
    },
)
async def mark_content_unread(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Mark content as unread by removing its read status."""
    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Delete read status
    result = db.execute(
        delete(ContentReadStatus).where(
            ContentReadStatus.content_id == content_id,
            ContentReadStatus.user_id == current_user.id
        )
    )
    db.commit()

    return {
        "status": "success",
        "content_id": content_id,
        "removed_records": result.rowcount,
    }


@router.post(
    "/bulk-mark-read",
    summary="Bulk mark content as read",
    description="Mark multiple content items as read in a single request.",
    responses={
        200: {"description": "Content items marked as read successfully"},
        400: {"description": "Invalid content IDs provided"},
        401: {"description": "Authentication required"},
    },
)
async def bulk_mark_read(
    request: BulkMarkReadRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
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
        current_user.id,
    )

    return {
        "status": "success",
        "marked_count": success_count,
        "failed_ids": failed_ids,
        "total_requested": len(request.content_ids),
    }


@router.get(
    "/recently-read/list",
    response_model=ContentListResponse,
    summary="Get recently read content",
    description=(
        "Retrieve all read content items sorted by read time "
        "(most recent first) with cursor-based pagination."
    ),
    responses={
        401: {"description": "Authentication required"},
    },
)
async def get_recently_read(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    cursor: str | None = Query(None, description="Pagination cursor for next page"),
    limit: int = Query(
        25,
        ge=1,
        le=100,
        description="Number of items per page (max 100)",
    ),
) -> ContentListResponse:
    """Get all recently read content with cursor-based pagination, sorted by read time."""
    from app.services import favorites, read_status

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
    read_content_ids = read_status.get_read_content_ids(db, current_user.id)

    # Get favorited content IDs
    favorite_content_ids = favorites.get_favorite_content_ids(db, current_user.id)

    # Query content joined with read status, ordered by read time
    query = db.query(Content, ContentReadStatus.read_at).join(
        ContentReadStatus, Content.id == ContentReadStatus.content_id
    )

    # Apply same visibility filters as other endpoints
    summarized_clause = Content.content_metadata["summary"].is_not(None) & (
        Content.content_metadata["summary"] != "null"
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
