"""CRUD endpoints for per-user scraper configurations."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, ValidationError
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
    get_scraper_config_stats,
    list_user_scraper_configs,
    update_user_scraper_config,
)

router = APIRouter(prefix="/scrapers", tags=["scrapers"])


class ScraperConfigStatsResponse(BaseModel):
    """Derived stats for a single scraper configuration."""

    total_count: int
    completed_count: int
    unread_count: int
    processing_count: int
    latest_processed_at: datetime | None = None
    latest_publication_at: datetime | None = None
    next_expected_at: datetime | None = None
    average_interval_hours: float | None = None
    interval_sample_size: int = 0


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
    stats: ScraperConfigStatsResponse | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "scraper_type": "substack",
                "display_name": "Import AI",
                "config": {"feed_url": "https://example.substack.com/feed"},
                "feed_url": "https://example.substack.com/feed",
                "limit": 10,
                "is_active": True,
                "created_at": "2025-06-24T12:00:00Z",
                "stats": {
                    "total_count": 8,
                    "completed_count": 7,
                    "unread_count": 3,
                    "processing_count": 1,
                    "latest_processed_at": "2026-03-30T21:30:00Z",
                    "latest_publication_at": "2026-03-30T20:00:00Z",
                    "next_expected_at": "2026-04-01T08:00:00Z",
                    "average_interval_hours": 24.0,
                    "interval_sample_size": 3,
                },
            }
        }
    )


def _coerce_limit(config: dict[str, Any]) -> int | None:
    limit = config.get("limit")
    if isinstance(limit, int) and 1 <= limit <= 100:
        return limit
    return None


def _serialize_scraper_config(
    config,
    *,
    stats: dict[str, Any] | None = None,
) -> ScraperConfigResponse:
    return ScraperConfigResponse(
        id=config.id,
        scraper_type=config.scraper_type,
        display_name=config.display_name,
        config=config.config or {},
        feed_url=(config.config or {}).get("feed_url"),
        limit=_coerce_limit(config.config or {}),
        is_active=config.is_active,
        created_at=config.created_at,
        stats=ScraperConfigStatsResponse(**stats) if stats is not None else None,
    )


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
    stats_by_config = get_scraper_config_stats(db, user_id=current_user.id, configs=configs)
    return [
        _serialize_scraper_config(
            config,
            stats=stats_by_config.get(config.id),
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

    stats_by_config = get_scraper_config_stats(db, user_id=current_user.id, configs=[record])
    return _serialize_scraper_config(record, stats=stats_by_config.get(record.id))


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

    stats_by_config = get_scraper_config_stats(db, user_id=current_user.id, configs=[record])
    return _serialize_scraper_config(record, stats=stats_by_config.get(record.id))


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

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "feed_url": "https://example.substack.com/feed",
                "feed_type": "substack",
                "display_name": "Example Newsletter",
            }
        }
    )


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

    try:
        create_payload = CreateUserScraperConfig(
            scraper_type=payload.feed_type,
            display_name=payload.display_name,
            config={
                "feed_url": payload.feed_url,
                "limit": DEFAULT_NEW_FEED_LIMIT,
            },
            is_active=True,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        record = create_user_scraper_config(db, current_user.id, create_payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    stats_by_config = get_scraper_config_stats(db, user_id=current_user.id, configs=[record])
    return _serialize_scraper_config(record, stats=stats_by_config.get(record.id))
