"""CRUD endpoints for per-user scraper configurations."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.db import get_db_session
from app.models.user import User
from app.services.scraper_configs import (
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
    is_active: bool
    created_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "scraper_type": "substack",
                "display_name": "Import AI",
                "config": {"feed_url": "https://example.substack.com/feed"},
                "is_active": True,
                "created_at": "2025-06-24T12:00:00Z",
            }
        }


@router.get("/", response_model=list[ScraperConfigResponse])
async def list_scraper_configs(
    db: Annotated[Session, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[ScraperConfigResponse]:
    """List scraper configurations for the current user."""
    configs = list_user_scraper_configs(db, current_user.id)
    return [
        ScraperConfigResponse(
            id=config.id,
            scraper_type=config.scraper_type,
            display_name=config.display_name,
            config=config.config or {},
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
