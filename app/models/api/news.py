"""Response models for the news-native API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.pagination import PaginationMetadata


class NewsDigestCitationResponse(BaseModel):
    """One supporting citation for a digest bullet."""

    news_item_id: int = Field(..., description="Supporting news item identifier")
    label: str | None = Field(None, description="Source label")
    title: str = Field(..., description="Best title for the cited item")
    url: str | None = Field(None, description="Preferred outward URL")
    article_url: str | None = Field(None, description="Canonical article URL when available")


class NewsDigestBulletResponse(BaseModel):
    """One persisted digest bullet."""

    id: int = Field(..., description="Bullet identifier")
    position: int = Field(..., ge=1, description="Bullet order within the digest")
    topic: str = Field(..., description="Short bullet topic")
    details: str = Field(..., description="Expanded bullet details")
    source_count: int = Field(..., ge=0, description="Number of cited items")
    citations: list[NewsDigestCitationResponse] = Field(default_factory=list)


class NewsDigestResponse(BaseModel):
    """Digest run detail payload."""

    id: int = Field(..., description="Digest identifier")
    timezone: str = Field(..., description="IANA timezone for rollover logic")
    title: str = Field(..., description="Digest title")
    summary: str = Field(..., description="Digest summary")
    source_count: int = Field(..., ge=0, description="Number of covered news items")
    group_count: int = Field(..., ge=0, description="Number of persisted bullets")
    trigger_reason: str = Field(..., description="Why this digest run was created")
    is_read: bool = Field(..., description="Whether the digest has been marked read")
    read_at: datetime | None = Field(None, description="When the digest was marked read")
    generated_at: datetime = Field(..., description="When the digest was generated")
    window_start_at: datetime = Field(..., description="Oldest included item ingest time")
    window_end_at: datetime = Field(..., description="Newest included item ingest time")
    bullets: list[NewsDigestBulletResponse] = Field(default_factory=list)


class NewsDigestListResponse(BaseModel):
    """Paginated digest listing."""

    digests: list[NewsDigestResponse] = Field(default_factory=list)
    meta: PaginationMetadata


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
