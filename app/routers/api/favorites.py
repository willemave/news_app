"""Favorites management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.core.db import get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.core.logging import get_logger
from app.domain.converters import content_to_domain
from app.models.metadata import ContentStatus, ContentType
from app.models.pagination import PaginationMetadata
from app.models.schema import Content
from app.models.user import User
from app.routers.api.models import ContentListResponse, ContentSummaryResponse
from app.utils.pagination import PaginationCursor

logger = get_logger(__name__)

router = APIRouter()


@router.post(
    "/{content_id}/favorite",
    summary="Toggle favorite status",
    description="Toggle the favorite status of a specific content item.",
    responses={
        200: {"description": "Favorite status toggled successfully"},
        404: {"description": "Content not found"},
        401: {"description": "Authentication required"},
    },
)
async def toggle_favorite(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Toggle favorite status for content."""
    from app.services import favorites

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Toggle favorite
    is_favorited, _ = favorites.toggle_favorite(db, content_id, current_user.id)
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
        401: {"description": "Authentication required"},
    },
)
async def unfavorite_content(
    content_id: Annotated[int, Path(..., description="Content ID", gt=0)],
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """Remove content from favorites."""
    from app.services import favorites

    # Check if content exists
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    # Remove from favorites
    removed = favorites.remove_favorite(db, content_id, current_user.id)
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
    responses={
        401: {"description": "Authentication required"},
    },
)
async def get_favorites(
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
    favorite_content_ids = favorites.get_favorite_content_ids(db, current_user.id)

    # Get read content IDs
    read_content_ids = read_status.get_read_content_ids(db, current_user.id)

    # Query favorited content
    if favorite_content_ids:
        query = db.query(Content).filter(Content.id.in_(favorite_content_ids))
        query = query.filter(Content.status == ContentStatus.COMPLETED.value)

        # Filter out "skip" classification articles
        query = query.filter(
            (Content.classification != "skip") | (Content.classification.is_(None))
        )

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
            discussion_url = (domain_content.metadata or {}).get("discussion_url")

            content_summaries.append(
                ContentSummaryResponse(
                    id=domain_content.id,
                    content_type=domain_content.content_type.value,
                    url=str(domain_content.url),
                    source_url=domain_content.source_url,
                    title=domain_content.display_title,
                    source=domain_content.source,
                    status=domain_content.status.value,
                    discussion_url=discussion_url,
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
            logger.warning(
                "Skipping content %s due to validation error: %s",
                c.id,
                e,
                extra={
                    "component": "favorites",
                    "operation": "list_favorites",
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
        last_item = contents[-1]  # Use original DB object
        next_cursor = PaginationCursor.encode_cursor(
            last_id=last_item.id,
            last_created_at=last_item.created_at,
            filters={},  # No filters for favorites
        )

    return ContentListResponse(
        contents=content_summaries,
        available_dates=[],  # Not needed for favorites list
        content_types=content_types,
        meta=PaginationMetadata(
            next_cursor=next_cursor,
            has_more=has_more,
            page_size=len(content_summaries),
            total=len(content_summaries),
        ),
    )
