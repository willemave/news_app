"""CRUD endpoints for per-user scraper configurations."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.constants import DEFAULT_NEW_FEED_LIMIT
from app.core.db import get_db_session, get_readonly_db_session
from app.core.deps import get_current_user
from app.models.user import User
from app.services.scraper_configs import (
    ALLOWED_SCRAPER_TYPES,
    CreateUserScraperConfig,
    UpdateUserScraperConfig,
    create_user_scraper_config,
    delete_user_scraper_config,
    list_user_scraper_configs,
    update_user_scraper_config,
)

router = APIRouter(prefix="/scrapers", tags=["scrapers"])


class ScraperConfigResponse(BaseModel):
    """Response model for scraper configs."""

    id: int
    scraper_type: str
    display_name: str | None = None
    config: dict[str, Any]
    feed_url: str | None = None
    limit: int | None = None
    is_active: bool
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "scraper_type": "substack",
                "display_name": "Import AI",
                "config": {"feed_url": "https://example.substack.com/feed"},
                "feed_url": "https://example.substack.com/feed",
                "limit": 10,
                "is_active": True,
                "created_at": "2025-06-24T12:00:00Z",
            }
        }


def _coerce_limit(config: dict[str, Any]) -> int | None:
    limit = config.get("limit")
    if isinstance(limit, int) and 1 <= limit <= 100:
        return limit
    return None


@router.get("/", response_model=list[ScraperConfigResponse])
async def list_scraper_configs(
    db: Annotated[Session, Depends(get_readonly_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    scraper_type: str | None = Query(None, alias="type"),
    types: str | None = Query(None, alias="types"),
) -> list[ScraperConfigResponse]:
    """List scraper configurations for the current user."""
    requested_types: set[str] = set()
    if scraper_type:
        requested_types.add(scraper_type)
    if types:
        requested_types.update({t for t in types.split(",") if t})

    if requested_types:
        invalid = requested_types.difference(ALLOWED_SCRAPER_TYPES)
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported scraper types: {', '.join(sorted(invalid))}",
            )

    configs = list_user_scraper_configs(
        db,
        current_user.id,
        allowed_types=requested_types or None,
    )
    return [
        ScraperConfigResponse(
            id=config.id,
            scraper_type=config.scraper_type,
            display_name=config.display_name,
            config=config.config or {},
            feed_url=(config.config or {}).get("feed_url"),
            limit=_coerce_limit(config.config or {}),
            is_active=config.is_active,
            created_at=config.created_at,
        )
        for config in configs
    ]


@router.post("/", response_model=ScraperConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_scraper_config(
    payload: CreateUserScraperConfig,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ScraperConfigResponse:
    """Create a scraper config for the current user."""
    try:
        record = create_user_scraper_config(db, current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ScraperConfigResponse(
        id=record.id,
        scraper_type=record.scraper_type,
        display_name=record.display_name,
        config=record.config or {},
        feed_url=(record.config or {}).get("feed_url"),
        limit=_coerce_limit(record.config or {}),
        is_active=record.is_active,
        created_at=record.created_at,
    )


@router.put("/{config_id}", response_model=ScraperConfigResponse)
async def update_scraper_config(
    config_id: int,
    payload: UpdateUserScraperConfig,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ScraperConfigResponse:
    """Update a scraper config belonging to the current user."""
    try:
        record = update_user_scraper_config(db, current_user.id, config_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ScraperConfigResponse(
        id=record.id,
        scraper_type=record.scraper_type,
        display_name=record.display_name,
        config=record.config or {},
        feed_url=(record.config or {}).get("feed_url"),
        limit=_coerce_limit(record.config or {}),
        is_active=record.is_active,
        created_at=record.created_at,
    )


@router.delete("/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scraper_config_endpoint(
    config_id: int,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    """Delete a scraper config for the current user."""
    try:
        delete_user_scraper_config(db, current_user.id, config_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


class SubscribeToFeedRequest(BaseModel):
    """Request to subscribe to a detected feed."""

    feed_url: str
    feed_type: str
    display_name: str | None = None

    class Config:
        json_schema_extra = {
            "example": {
                "feed_url": "https://example.substack.com/feed",
                "feed_type": "substack",
                "display_name": "Example Newsletter",
            }
        }


@router.post(
    "/subscribe", response_model=ScraperConfigResponse, status_code=status.HTTP_201_CREATED
)
async def subscribe_to_feed(
    payload: SubscribeToFeedRequest,
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ScraperConfigResponse:
    """Subscribe to a feed detected from content.

    Convenience endpoint that creates a scraper config from a detected feed.
    """
    if payload.feed_type not in ALLOWED_SCRAPER_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported feed type: {payload.feed_type}",
        )

    create_payload = CreateUserScraperConfig(
        scraper_type=payload.feed_type,
        display_name=payload.display_name,
        config={
            "feed_url": payload.feed_url,
            "limit": DEFAULT_NEW_FEED_LIMIT,
        },
        is_active=True,
    )

    try:
        record = create_user_scraper_config(db, current_user.id, create_payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ScraperConfigResponse(
        id=record.id,
        scraper_type=record.scraper_type,
        display_name=record.display_name,
        config=record.config or {},
        feed_url=(record.config or {}).get("feed_url"),
        limit=_coerce_limit(record.config or {}),
        is_active=record.is_active,
        created_at=record.created_at,
    )
