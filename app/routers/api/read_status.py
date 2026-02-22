"""Read status management endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, delete, or_
from sqlalchemy.orm import Session

from app.core.db import get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.models.metadata import ContentType
from app.models.pagination import PaginationMetadata
from app.models.schema import Content, ContentReadStatus
from app.models.user import User
from app.presenters.content_presenter import (
    build_content_summary_response,
    build_domain_content,
    resolve_image_urls,
)
from app.repositories.content_feed_query import build_user_feed_query
from app.routers.api.models import BulkMarkReadRequest, ContentListResponse
from app.utils.pagination import PaginationCursor

logger = get_logger(__name__)

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

    logger.info(
        "[API] POST /{content_id}/mark-read called | user_id=%s content_id=%s",
        current_user.id,
        content_id,
    )

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        logger.warning(
            "[API] mark-read failed: content not found | user_id=%s content_id=%s",
            current_user.id,
            content_id,
        )
        raise HTTPException(status_code=404, detail="Content not found")

    # Mark as read
    result = read_status.mark_content_as_read(db, content_id, current_user.id)
    if result:
        logger.info(
            "[API] mark-read success | user_id=%s content_id=%s content_type=%s",
            current_user.id,
            content_id,
            content.content_type,
        )
        return {"status": "success", "content_id": content_id}
    else:
        logger.error(
            "[API] mark-read failed: service returned None | user_id=%s content_id=%s",
            current_user.id,
            content_id,
        )
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
    logger.info(
        "[API] DELETE /{content_id}/mark-unread called | user_id=%s content_id=%s",
        current_user.id,
        content_id,
    )

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        logger.warning(
            "[API] mark-unread failed: content not found | user_id=%s content_id=%s",
            current_user.id,
            content_id,
        )
        raise HTTPException(status_code=404, detail="Content not found")

    # Delete read status
    result = db.execute(
        delete(ContentReadStatus).where(
            ContentReadStatus.content_id == content_id, ContentReadStatus.user_id == current_user.id
        )
    )
    db.commit()

    logger.info(
        "[API] mark-unread success | user_id=%s content_id=%s removed_records=%s",
        current_user.id,
        content_id,
        result.rowcount,
    )

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

    logger.info(
        "[API] POST /bulk-mark-read called | user_id=%s content_ids=%s count=%s",
        current_user.id,
        request.content_ids,
        len(request.content_ids),
    )

    # Validate that all content IDs exist
    existing_ids = db.query(Content.id).filter(Content.id.in_(request.content_ids)).all()
    existing_ids = {row[0] for row in existing_ids}

    invalid_ids = set(request.content_ids) - existing_ids
    if invalid_ids:
        logger.warning(
            "[API] bulk-mark-read failed: invalid IDs | user_id=%s invalid_ids=%s",
            current_user.id,
            sorted(invalid_ids),
        )
        raise HTTPException(status_code=400, detail=f"Invalid content IDs: {sorted(invalid_ids)}")

    success_count, failed_ids = read_status.mark_contents_as_read(
        db,
        request.content_ids,
        current_user.id,
    )

    logger.info(
        "[API] bulk-mark-read complete | user_id=%s marked=%s failed=%s total=%s",
        current_user.id,
        success_count,
        len(failed_ids),
        len(request.content_ids),
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
    db: Annotated[Session, Depends(get_readonly_db_session)],
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
    logger.info(
        "[API] GET /recently-read/list called | user_id=%s cursor=%s limit=%s",
        current_user.id,
        cursor[:20] + "..." if cursor else None,
        limit,
    )

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
            logger.debug(
                "[API] recently-read cursor decoded | last_id=%s last_read_at=%s",
                last_id,
                last_read_at,
            )
        except ValueError as e:
            logger.warning(
                "[API] recently-read invalid cursor | user_id=%s error=%s",
                current_user.id,
                str(e),
            )
            raise HTTPException(status_code=400, detail=str(e)) from e

    query = build_user_feed_query(db, current_user.id, mode="recently_read").add_columns(
        ContentReadStatus.read_at.label("read_at")
    )

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
    # Convert to response format
    content_summaries = []
    rows = []
    for c, is_read, is_favorited, read_at in results:
        rows.append((c, is_read, is_favorited, read_at))

    for c, is_read, is_favorited, _read_at in rows:
        try:
            domain_content = build_domain_content(c)
            image_url, thumbnail_url = resolve_image_urls(domain_content)
            content_summaries.append(
                build_content_summary_response(
                    content=c,
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
                c.id,
                e,
                extra={
                    "component": "read_status_api",
                    "operation": "recently_read_list",
                    "item_id": c.id,
                    "context_data": {"content_id": c.id},
                },
            )
            continue

    # Get content types for filter
    content_types = [ct.value for ct in ContentType]

    # Generate next cursor if there are more results
    next_cursor = None
    if has_more and content_summaries:
        last_item_content, _is_read, _is_favorited, last_item_read_at = rows[-1]
        next_cursor = PaginationCursor.encode_cursor(
            last_id=last_item_content.id,
            last_created_at=last_item_content.created_at,
            filters={"last_read_at": last_item_read_at.isoformat()},
        )

    logger.info(
        "[API] GET /recently-read/list complete | user_id=%s returned=%s has_more=%s",
        current_user.id,
        len(content_summaries),
        has_more,
    )

    return ContentListResponse(
        contents=content_summaries,
        available_dates=[],  # Not needed for recently read list
        content_types=content_types,
        meta=PaginationMetadata(
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=len(content_summaries),
            total=len(content_summaries),
        ),
    )
