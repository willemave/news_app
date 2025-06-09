"""
Pydantic schemas for the news app.
"""
from pydantic import BaseModel


class ArticleSummary(BaseModel):
    """Schema for article summaries."""
    short_summary: str
    detailed_summary: str


class FilterResult(BaseModel):
    """Schema for article filtering results."""
    matches: bool
    reason: str


class PodcastSummary(BaseModel):
    """Schema for podcast summaries."""
    short_summary: str
    detailed_summary: str
