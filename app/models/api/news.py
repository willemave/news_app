"""Response models for the news-native API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NewsItemResponse(BaseModel):
    """Visible news item detail payload."""

    id: int
    visibility_scope: str
    owner_user_id: int | None = None
    platform: str | None = None
    source_type: str | None = None
    source_label: str | None = None
    source_external_id: str | None = None
    canonical_item_url: str | None = None
    canonical_story_url: str | None = None
    article_url: str | None = None
    article_title: str | None = None
    article_domain: str | None = None
    discussion_url: str | None = None
    summary_title: str | None = None
    summary_key_points: list[str] = Field(default_factory=list)
    summary_text: str | None = None
    status: str
    published_at: datetime | None = None
    ingested_at: datetime
    processed_at: datetime | None = None
    raw_metadata: dict[str, Any] = Field(default_factory=dict)


class ConvertNewsItemResponse(BaseModel):
    """Response for converting a news item into long-form article content."""

    status: str = Field(default="success")
    news_item_id: int
    new_content_id: int
    already_exists: bool
    message: str
