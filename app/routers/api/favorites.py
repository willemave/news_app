"""Favorites management endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from app.application.commands import toggle_favorite as toggle_favorite_command
from app.application.queries import get_favorites as get_favorites_query
from app.core.db import get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.models.schema import Content
from app.models.user import User
from app.routers.api.models import ContentListResponse

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
    return toggle_favorite_command.execute(db, user_id=current_user.id, content_id=content_id)


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
    content = db.query(Content).filter(Content.id == content_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")

    from app.repositories import favorites_repository

    removed = favorites_repository.remove_favorite(db, content_id, current_user.id)
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
    return get_favorites_query.execute(
        db,
        user_id=current_user.id,
        cursor=cursor,
        limit=limit,
    )
