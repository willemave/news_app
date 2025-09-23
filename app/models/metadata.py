"""
Unified metadata models for content types.
Merges functionality from app/schemas/metadata.py and app/domain/content.py.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    TypeAdapter,
    field_validator,
)


# Enums from app/domain/content.py
class ContentType(str, Enum):
    ARTICLE = "article"
    PODCAST = "podcast"
    NEWS = "news"


class ContentStatus(str, Enum):
    NEW = "new"
    PENDING = "pending"  # Legacy status still in database
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class ContentClassification(str, Enum):
    TO_READ = "to_read"
    SKIP = "skip"


# Structured summary components from app/schemas/metadata.py
class SummaryBulletPoint(BaseModel):
    """Individual bullet point in a structured summary."""

    text: str = Field(..., min_length=10, max_length=500)
    category: str | None = Field(
        None,
        description=(
            "Category of the bullet point (e.g., 'key_finding', 'methodology', 'conclusion')"
        ),
    )


class ContentQuote(BaseModel):
    """Notable quote extracted from content."""

    text: str = Field(..., min_length=10, max_length=5000)
    context: str | None = Field(None, description="Context or attribution for the quote")


class StructuredSummary(BaseModel):
    """Structured summary with bullet points and quotes."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "AI Advances in Natural Language Processing Transform Industry",
                "overview": "Brief overview of the content",
                "bullet_points": [
                    {"text": "Key point 1", "category": "key_finding"},
                    {"text": "Key point 2", "category": "methodology"},
                ],
                "quotes": [{"text": "Notable quote from the content", "context": "Author Name"}],
                "topics": ["AI", "Technology", "Innovation"],
                "summarization_date": "2025-06-14T10:30:00Z",
                "full_markdown": (
                    "# AI Advances in Natural Language Processing\n\n"
                    "Full article content in markdown format..."
                ),
            }
        }
    )

    title: str = Field(
        ..., min_length=5, max_length=1000, description="Descriptive title for the content"
    )
    overview: str = Field(
        ..., min_length=50, description="Brief overview paragraph (longer for podcasts)"
    )
    bullet_points: list[SummaryBulletPoint] = Field(..., min_items=3, max_items=50)
    quotes: list[ContentQuote] = Field(default_factory=list, max_items=50)
    topics: list[str] = Field(default_factory=list, max_items=50)
    summarization_date: datetime = Field(default_factory=datetime.utcnow)
    classification: str = Field(
        default="to_read", description="Content classification: 'to_read' or 'skip'"
    )
    full_markdown: str = Field(
        default="", description="Full article content formatted as clean, readable markdown"
    )


# News digest summary used for fast-scanning feeds

class NewsSummary(BaseModel):
    """Compact summary payload for quick-glance news content."""

    model_config = ConfigDict(
        extra="allow",
        json_schema_extra={
            "additionalProperties": False,
            "example": {
                "title": "Techmeme: OpenAI ships GPT-5 with native agents",
                "article_url": "https://example.com/story",
                "bullet_points": [
                    "OpenAI launches GPT-5 with native agent orchestration",
                    "Developers get first-party workflows that replace plug-ins",
                    "Initial rollout targets enterprise customers later expanding to prosumers",
                ],
                "overview": (
                    "OpenAI debuts GPT-5 with native multi-agent features and "
                    "enterprise-first rollout."
                ),
                "classification": "to_read",
                "summarization_date": "2025-09-22T10:30:00Z",
            }
        },
    )

    title: str | None = Field(
        None, min_length=5, max_length=240, description="Generated headline for the digest"
    )
    article_url: str | None = Field(
        None,
        min_length=1,
        max_length=2083,
        description="Canonical article URL referenced by the digest",
    )
    key_points: list[str] = Field(
        default_factory=list,
        min_length=0,
        max_length=6,
        description="Headline-ready bullet points summarizing the article",
        validation_alias=AliasChoices("key_points", "bullet_points"),
        serialization_alias="bullet_points",
    )
    summary: str | None = Field(
        None,
        min_length=0,
        max_length=500,
        description="Optional short overview paragraph",
        validation_alias=AliasChoices("summary", "overview"),
        serialization_alias="overview",
    )
    classification: str = Field(
        default="to_read",
        pattern="^(to_read|skip)$",
        description="Read recommendation classification",
    )
    summarization_date: datetime = Field(
        default_factory=datetime.utcnow,
        description="Timestamp when the digest was generated",
    )

    @field_validator("article_url")
    @classmethod
    def validate_article_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        adapter = TypeAdapter(HttpUrl)
        return str(adapter.validate_python(value))


class NewsArticleMetadata(BaseModel):
    """Details about the linked article for a news item."""

    url: HttpUrl = Field(..., description="Canonical article URL to summarize")
    title: str | None = Field(None, max_length=500)
    source_domain: str | None = Field(None, max_length=200)


class NewsAggregatorMetadata(BaseModel):
    """Context about the upstream aggregator (HN, Techmeme, Twitter)."""

    name: str | None = Field(None, max_length=120)
    title: str | None = Field(None, max_length=500)
    url: HttpUrl | None = Field(None, description="Link back to the aggregator discussion/thread")
    external_id: str | None = Field(None, max_length=200)
    author: str | None = Field(None, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Base metadata with source field added
class BaseContentMetadata(BaseModel):
    """Base metadata fields common to all content types."""

    model_config = ConfigDict(extra="allow")

    # NEW: Source field to track content origin
    source: str | None = Field(
        None, description="Source of content (e.g., substack name, podcast name, subreddit name)"
    )

    summary: StructuredSummary | NewsSummary | None = Field(
        None, description="AI-generated structured summary"
    )
    word_count: int | None = Field(None, ge=0)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: StructuredSummary | NewsSummary | dict[str, Any] | None):
        """Normalize summary payloads into structured models."""
        if value is None or isinstance(value, StructuredSummary | NewsSummary):
            return value
        if isinstance(value, dict):
            summary_type = value.get("summary_type")
            if summary_type == "news_digest":
                return NewsSummary.model_validate(value)
            try:
                return StructuredSummary.model_validate(value)
            except Exception:
                return NewsSummary.model_validate(value)
        raise ValueError("Summary must be StructuredSummary, NewsSummary, or dict")


# Article metadata from app/schemas/metadata.py
class ArticleMetadata(BaseContentMetadata):
    """Metadata specific to articles."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "Import AI",
                "content": "Full article text...",
                "author": "John Doe",
                "publication_date": "2025-06-14T00:00:00",
                "content_type": "html",
                "final_url_after_redirects": "https://example.com/article",
                "word_count": 1500,
                "summary": {
                    "overview": "Brief overview of the article content",
                    "bullet_points": [
                        {"text": "Key point 1", "category": "key_finding"},
                        {"text": "Key point 2", "category": "methodology"},
                        {"text": "Key point 3", "category": "conclusion"},
                    ],
                    "quotes": [
                        {"text": "Notable quote from the article", "context": "Author Name"}
                    ],
                    "topics": ["Technology", "Innovation"],
                    "summarization_date": "2025-06-14T10:30:00Z",
                },
            }
        }
    )

    content: str | None = Field(None, description="Full article text content")

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        """Allow empty string for legacy data but convert to None."""
        if v == "":
            return None
        return v

    author: str | None = Field(None, max_length=200)
    publication_date: datetime | None = None
    content_type: str = Field(default="html", pattern="^(pdf|html|text|markdown)$")
    final_url_after_redirects: str | None = Field(None, max_length=2000)


# Podcast metadata from app/schemas/metadata.py
class PodcastMetadata(BaseContentMetadata):
    """Metadata specific to podcasts."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "Lenny's Podcast",
                "audio_url": "https://example.com/episode.mp3",
                "transcript": "Full transcript text...",
                "duration": 3600,
                "episode_number": 42,
                "summary": {
                    "overview": "Brief overview of the podcast episode",
                    "bullet_points": [
                        {"text": "Key topic discussed", "category": "key_finding"},
                        {"text": "Important insight shared", "category": "insight"},
                        {"text": "Main conclusion", "category": "conclusion"},
                    ],
                    "quotes": [
                        {"text": "Memorable quote from the episode", "context": "Speaker Name"}
                    ],
                    "topics": ["Podcast", "Discussion", "Interview"],
                    "summarization_date": "2025-06-14T10:30:00Z",
                },
            }
        }
    )

    audio_url: str | None = Field(None, max_length=2000, description="URL to the audio file")
    transcript: str | None = Field(None, description="Full transcript text")
    duration: int | None = Field(None, ge=0, description="Duration in seconds")
    episode_number: int | None = Field(None, ge=0)
    
    # YouTube-specific fields
    video_url: str | None = Field(None, max_length=2000, description="Original YouTube video URL")
    video_id: str | None = Field(None, max_length=50, description="YouTube video ID")
    channel_name: str | None = Field(None, max_length=200, description="YouTube channel name")
    thumbnail_url: str | None = Field(None, max_length=2000, description="Video thumbnail URL")
    view_count: int | None = Field(None, ge=0, description="Number of views")
    like_count: int | None = Field(None, ge=0, description="Number of likes")
    has_transcript: bool | None = Field(None, description="Whether transcript is available")


class NewsMetadata(BaseContentMetadata):
    """Metadata structure for single-link news content."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "example.com",
                "platform": "hackernews",
                "article": {
                    "url": "https://example.com/story",
                    "title": "Example Story",
                    "source_domain": "example.com",
                },
                "aggregator": {
                    "name": "Hacker News",
                    "url": "https://news.ycombinator.com/item?id=123",
                    "external_id": "123",
                    "metadata": {"score": 420},
                },
                "summary": {
                    "title": "Techmeme: OpenAI ships GPT-5 with native agents",
                    "article_url": "https://example.com/story",
                    "bullet_points": [
                        "OpenAI launches GPT-5 with native agent orchestration",
                        "Developers get first-party workflows that replace plug-ins",
                        "Initial rollout targets enterprise customers later expanding to prosumers",
                    ],
                    "overview": (
                        "OpenAI debuts GPT-5 with native multi-agent features and enterprise-first "
                        "rollout."
                    ),
                    "classification": "to_read",
                    "summarization_date": "2025-09-22T10:30:00Z",
                },
            }
        }
    )

    article: NewsArticleMetadata = Field(..., description="Primary article information")
    aggregator: NewsAggregatorMetadata | None = Field(
        None, description="Upstream aggregator context"
    )
    discovery_time: datetime | None = Field(
        default_factory=datetime.utcnow, description="When the item was discovered"
    )


# Processing result from app/domain/content.py
class ProcessingResult(BaseModel):
    """Result from content processing."""

    success: bool
    content_type: ContentType
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    internal_links: list[str] = Field(default_factory=list)

    class Config:
        frozen = True


# Processing error from app/schemas/metadata.py
class ProcessingError(BaseModel):
    """Error information for failed processing."""

    error: str = Field(..., description="Error message")
    error_type: str = Field(default="unknown", pattern="^(retryable|non_retryable|unknown)$")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ContentData wrapper from app/domain/content.py with enhancements
class ContentData(BaseModel):
    """
    Unified content data model for passing between layers.
    """

    model_config = ConfigDict(
        ignored_types=(property,), json_encoders={datetime: lambda value: value.isoformat()}
    )

    id: int | None = None
    content_type: ContentType
    url: HttpUrl
    title: str | None = None
    status: ContentStatus = ContentStatus.NEW
    metadata: dict[str, Any] = Field(default_factory=dict)

    platform: str | None = Field(default=None, exclude=True)
    source: str | None = Field(default=None, exclude=True)
    is_aggregate: bool = False

    # Processing metadata
    error_message: str | None = None
    retry_count: int = 0

    # Timestamps
    created_at: datetime | None = None
    processed_at: datetime | None = None
    publication_date: datetime | None = None

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v, info):
        """Ensure metadata matches content type."""
        if info.data:
            content_type = info.data.get("content_type")

            # Clean up empty strings in metadata
            if isinstance(v, dict):
                cleaned_v = {}
                for key, value in v.items():
                    if value == "":
                        cleaned_v[key] = None
                    else:
                        cleaned_v[key] = value
                v = cleaned_v

            if content_type == ContentType.ARTICLE:
                # Validate article metadata
                try:
                    ArticleMetadata(**v)
                except Exception as e:
                    raise ValueError(f"Invalid article metadata: {e}") from e
            elif content_type == ContentType.PODCAST:
                # Validate podcast metadata
                try:
                    PodcastMetadata(**v)
                except Exception as e:
                    raise ValueError(f"Invalid podcast metadata: {e}") from e
            elif content_type == ContentType.NEWS:
                try:
                    NewsMetadata(**v)
                except Exception as e:
                    raise ValueError(f"Invalid news metadata: {e}") from e
        return v

    def to_article_metadata(self) -> ArticleMetadata:
        """Convert metadata to ArticleMetadata."""
        if self.content_type != ContentType.ARTICLE:
            raise ValueError("Not an article")
        return ArticleMetadata(**self.metadata)

    def to_podcast_metadata(self) -> PodcastMetadata:
        """Convert metadata to PodcastMetadata."""
        if self.content_type != ContentType.PODCAST:
            raise ValueError("Not a podcast")
        return PodcastMetadata(**self.metadata)

    def to_news_metadata(self) -> NewsMetadata:
        """Convert metadata to NewsMetadata."""
        if self.content_type != ContentType.NEWS:
            raise ValueError("Not news content")
        return NewsMetadata(**self.metadata)

    @property
    def summary(self) -> str | None:
        """Get summary text (either simple or overview from structured)."""
        summary_data = self.metadata.get("summary")
        if not summary_data:
            if self.content_type == ContentType.NEWS:
                excerpt = self.metadata.get("excerpt")
                if excerpt:
                    return excerpt
                items = self.news_items
                if items:
                    first = items[0]
                    if isinstance(first, dict):
                        return first.get("summary") or first.get("title")
            return None
        if isinstance(summary_data, str):
            return summary_data
        if isinstance(summary_data, dict):
            if "overview" in summary_data:
                return summary_data.get("overview", "")
            if summary_data.get("summary_type") == "news_digest":
                return summary_data.get("summary")
        return None

    @property
    def display_title(self) -> str:
        """Get title to display - prefer summary title over content title."""
        summary_data = self.metadata.get("summary")
        if isinstance(summary_data, dict) and summary_data.get("title"):
            return summary_data["title"]
        return self.title or "Untitled"

    @property
    def short_summary(self) -> str | None:
        """Get short version of summary for list view."""
        summary = self.metadata.get("summary")
        if isinstance(summary, dict):
            if "overview" in summary:
                return summary.get("overview")
            if summary.get("summary_type") == "news_digest":
                return summary.get("summary")
        if isinstance(summary, str):
            return summary
        return None

    @property
    def structured_summary(self) -> dict[str, Any] | None:
        """Get structured summary if available."""
        summary_data = self.metadata.get("summary")
        if isinstance(summary_data, dict) and "bullet_points" in summary_data:
            return summary_data
        return None

    @property
    def bullet_points(self) -> list[dict[str, str]]:
        """Get bullet points from structured summary."""
        if self.structured_summary:
            return self.structured_summary.get("bullet_points", [])
        return []

    @property
    def quotes(self) -> list[dict[str, str]]:
        """Get quotes from structured summary."""
        if self.structured_summary:
            return self.structured_summary.get("quotes", [])
        return []

    @property
    def topics(self) -> list[str]:
        """Get topics from structured summary."""
        if self.structured_summary:
            return self.structured_summary.get("topics", [])
        return self.metadata.get("topics", [])

    @property
    def transcript(self) -> str | None:
        """Get transcript for podcasts."""
        if self.content_type == ContentType.PODCAST:
            return self.metadata.get("transcript")
        return None

    @property
    def source(self) -> str | None:  # noqa: F811
        """Get content source (substack name, podcast name, subreddit)."""
        return self.metadata.get("source")

    @property
    def platform(self) -> str | None:  # noqa: F811
        """Get content platform (twitter, substack, youtube, etc)."""
        return self.metadata.get("platform")

    @property
    def full_markdown(self) -> str | None:
        """Get full article content formatted as markdown from StructuredSummary."""
        summary_data = self.metadata.get("summary")
        if isinstance(summary_data, dict):
            return summary_data.get("full_markdown")
        return None

    @property
    def news_items(self) -> list[dict[str, Any]]:
        """Return news items list when available."""
        if self.content_type != ContentType.NEWS:
            return []
        items = self.metadata.get("items")
        return items if isinstance(items, list) else []

    @property
    def rendered_news_markdown(self) -> str | None:
        """Return rendered markdown for aggregate news."""
        if self.content_type != ContentType.NEWS:
            return None
        rendered = self.metadata.get("rendered_markdown")
        if isinstance(rendered, str) and rendered.strip():
            return rendered
        return None

    def model_dump(self, *args, **kwargs):  # type: ignore[override]
        excludes = kwargs.pop("exclude", set())
        excludes = set(excludes) | {"platform", "source"}
        data = super().model_dump(*args, exclude=excludes, **kwargs)
        metadata = data.get("metadata") or {}
        platform = metadata.get("platform")
        source = metadata.get("source")
        if platform is not None:
            data["platform"] = platform
        if source is not None:
            data["source"] = source
        return data


# Helper functions from app/schemas/metadata.py
def validate_content_metadata(
    content_type: str, metadata: dict
) -> ArticleMetadata | PodcastMetadata | NewsMetadata:
    """
    Validate and parse metadata based on content type.

    Args:
        content_type: Type of content ('article' or 'podcast')
        metadata: Raw metadata dictionary

    Returns:
        Validated metadata model

    Raises:
        ValueError: If content_type is unknown
        ValidationError: If metadata doesn't match schema
    """
    # Remove error fields if present (they should be in separate columns)
    cleaned_metadata = {k: v for k, v in metadata.items() if k not in ["error", "error_type"]}

    if content_type == ContentType.ARTICLE.value:
        return ArticleMetadata(**cleaned_metadata)
    if content_type == ContentType.PODCAST.value:
        return PodcastMetadata(**cleaned_metadata)
    if content_type == ContentType.NEWS.value:
        return NewsMetadata(**cleaned_metadata)
    raise ValueError(f"Unknown content type: {content_type}")
