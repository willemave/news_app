"""
Unified metadata models for content types.
Merges functionality from app/schemas/metadata.py and app/domain/content.py.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from enum import Enum
from typing import Any
from urllib.parse import urlparse

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
    UNKNOWN = "unknown"  # URL pending LLM analysis to determine type


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


class InterleavedInsight(BaseModel):
    """Single insight with bundled topic, text, and supporting quote."""

    topic: str = Field(
        ..., min_length=2, max_length=50, description="Key topic or theme (2-5 words)"
    )
    insight: str = Field(..., min_length=50, description="Substantive insight (2-3 sentences)")
    supporting_quote: str | None = Field(
        None, min_length=20, description="Direct quote (20+ words) supporting the insight"
    )
    quote_attribution: str | None = Field(
        None, description="Who said the quote - author, speaker, or publication"
    )


class InterleavedSummary(BaseModel):
    """Interleaved summary format that weaves topics with supporting quotes."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "summary_type": "interleaved",
                "title": "AI Advances in Natural Language Processing",
                "hook": (
                    "This article explores groundbreaking developments in NLP "
                    "that could reshape how we interact with technology."
                ),
                "insights": [
                    {
                        "topic": "Performance Gains",
                        "insight": (
                            "The new model achieves 40% improvement in accuracy "
                            "on standard benchmarks while using half the compute."
                        ),
                        "supporting_quote": (
                            "We were surprised by the magnitude of the improvements, "
                            "which exceeded our initial expectations significantly."
                        ),
                        "quote_attribution": "Lead Researcher",
                    }
                ],
                "takeaway": (
                    "These developments signal a fundamental shift in how AI systems "
                    "process and understand human language."
                ),
                "classification": "to_read",
                "summarization_date": "2025-06-14T10:30:00Z",
            }
        }
    )

    summary_type: str = Field(
        default="interleaved", description="Discriminator field for iOS client"
    )
    title: str = Field(
        ..., min_length=5, max_length=1000, description="Descriptive title for the content"
    )
    hook: str = Field(
        ..., min_length=80, description="Opening hook (2-3 sentences) capturing the main story"
    )
    insights: list[InterleavedInsight] = Field(
        ..., min_length=3, max_length=8, description="Key insights with supporting quotes"
    )
    takeaway: str = Field(
        ..., min_length=80, description="Final takeaway (2-3 sentences) for the reader"
    )
    classification: str = Field(
        default="to_read",
        pattern="^(to_read|skip)$",
        description="Content classification: 'to_read' or 'skip'",
    )
    summarization_date: datetime = Field(default_factory=datetime.utcnow)


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
                "questions": [
                    "How might these AI advances impact existing NLP applications?",
                    "What are the potential ethical implications of this technology?",
                ],
                "counter_arguments": [
                    (
                        "Critics argue that the claimed improvements may not generalize "
                        "beyond specific benchmarks"
                    ),
                    "Alternative approaches like symbolic AI might offer more explainability",
                ],
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
    questions: list[str] = Field(
        default_factory=list,
        max_items=10,
        description="Questions to help readers think critically about the content",
    )
    counter_arguments: list[str] = Field(
        default_factory=list,
        max_items=10,
        description="Counter-arguments or alternative perspectives to the main claims",
    )
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
            },
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

    summary: StructuredSummary | InterleavedSummary | NewsSummary | None = Field(
        None, description="AI-generated structured summary"
    )
    word_count: int | None = Field(None, ge=0)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(
        cls, value: StructuredSummary | InterleavedSummary | NewsSummary | dict[str, Any] | None
    ):
        """Normalize summary payloads into structured models."""
        if value is None or isinstance(value, (StructuredSummary, InterleavedSummary, NewsSummary)):
            return value
        if isinstance(value, dict):
            summary_type = value.get("summary_type")
            if summary_type == "interleaved":
                return InterleavedSummary.model_validate(value)
            if summary_type == "news_digest":
                return NewsSummary.model_validate(value)
            try:
                return StructuredSummary.model_validate(value)
            except Exception:
                return NewsSummary.model_validate(value)
        raise ValueError(
            "Summary must be StructuredSummary, InterleavedSummary, NewsSummary, or dict"
        )


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
        """Get structured or interleaved summary if available."""
        summary_data = self.metadata.get("summary")
        # Return if it's a structured summary (has bullet_points)
        # or an interleaved summary (has insights)
        if isinstance(summary_data, dict) and (
            "bullet_points" in summary_data or "insights" in summary_data
        ):
            return summary_data
        return None

    @property
    def bullet_points(self) -> list[dict[str, str]]:
        """Get bullet points from structured or interleaved summary.

        For interleaved summaries, converts insights to bullet point format.
        """
        if not self.structured_summary:
            return []

        # Standard structured summary with bullet_points
        if "bullet_points" in self.structured_summary:
            return self.structured_summary.get("bullet_points", [])

        # Interleaved summary - convert insights to bullet point format
        insights = self.structured_summary.get("insights", [])
        if insights:
            return [
                {"text": ins.get("insight", ""), "category": ins.get("topic", "")}
                for ins in insights
                if ins.get("insight")
            ]

        return []

    @property
    def quotes(self) -> list[dict[str, str]]:
        """Get quotes from structured or interleaved summary.

        For interleaved summaries, extracts supporting quotes from insights.
        """
        if not self.structured_summary:
            return []

        # Standard structured summary with quotes
        if "quotes" in self.structured_summary:
            return self.structured_summary.get("quotes", [])

        # Interleaved summary - extract supporting quotes from insights
        insights = self.structured_summary.get("insights", [])
        quotes = []
        for ins in insights:
            quote_text = ins.get("supporting_quote")
            if quote_text:
                quotes.append(
                    {
                        "text": quote_text,
                        "context": ins.get("quote_attribution", ins.get("topic", "")),
                    }
                )
        return quotes

    @property
    def topics(self) -> list[str]:
        """Get topics from structured or interleaved summary.

        For interleaved summaries, extracts unique topic names from insights.
        """
        if self.structured_summary:
            # Standard topics array
            if "topics" in self.structured_summary:
                return self.structured_summary.get("topics", [])

            # Interleaved summary - extract unique topics from insights
            insights = self.structured_summary.get("insights", [])
            if insights:
                seen = set()
                topics = []
                for ins in insights:
                    topic = ins.get("topic")
                    if topic and topic not in seen:
                        seen.add(topic)
                        topics.append(topic)
                return topics

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
        enriched = _ensure_news_article_metadata(cleaned_metadata)
        return NewsMetadata(**enriched)
    if content_type == ContentType.UNKNOWN.value:
        # UNKNOWN content uses minimal ArticleMetadata as placeholder
        return ArticleMetadata(**cleaned_metadata)
    raise ValueError(f"Unknown content type: {content_type}")


def _ensure_news_article_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Backfill article fields for legacy news metadata lacking required structure."""

    working_copy: dict[str, Any] = deepcopy(metadata)

    article_data = working_copy.get("article")
    if not isinstance(article_data, dict):
        article_data = {}

    article_url = _first_valid_url(
        article_data.get("url"),
        _first_item_url(working_copy.get("items")),
        working_copy.get("primary_url"),
        working_copy.get("url"),
    )

    if not article_url:
        aggregator_url = None
        aggregator = working_copy.get("aggregator")
        if isinstance(aggregator, dict):
            aggregator_url = aggregator.get("url")
        article_url = _first_valid_url(aggregator_url)

    if article_url:
        article_data.setdefault("url", article_url)
        article_data.setdefault("source_domain", _extract_source_domain(article_url))

    title_candidates: list[str | None] = [
        article_data.get("title"),
        _first_item_title(working_copy.get("items")),
        _summary_title_hint(working_copy.get("summary")),
    ]
    for candidate in title_candidates:
        if isinstance(candidate, str) and candidate.strip():
            article_data.setdefault("title", candidate.strip())
            break

    if article_data.get("url"):
        working_copy["article"] = article_data

    return working_copy


def _first_valid_url(*candidates: str | None) -> str | None:
    for url in candidates:
        if not isinstance(url, str):
            continue
        trimmed = url.strip()
        if trimmed and trimmed.lower().startswith(("http://", "https://")):
            return trimmed
    return None


def _first_item_url(items: Any) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get("url") or item.get("expanded_url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def _first_item_title(items: Any) -> str | None:
    if not isinstance(items, list):
        return None
    for item in items:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("summary")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return None


def _summary_title_hint(summary: Any) -> str | None:
    if isinstance(summary, dict):
        for key in ("title", "headline", "overview"):
            value = summary.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    elif isinstance(summary, str) and summary.strip():
        return summary.strip().splitlines()[0]
    return None


def _extract_source_domain(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except Exception:
        return None

    domain = parsed.netloc.lower()
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None
