"""Structured LLM outputs for news-native digest generation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NewsDigestBulletDraft(BaseModel):
    """One grounded digest bullet generated from a cluster."""

    topic: str = Field(..., min_length=3, max_length=240)
    details: str = Field(..., min_length=20)
    news_item_ids: list[int] = Field(default_factory=list, min_length=1)


class NewsDigestHeaderDraft(BaseModel):
    """Digest-level title and summary generated from final bullets."""

    title: str = Field(..., min_length=3, max_length=240)
    summary: str = Field(..., min_length=20, max_length=800)
