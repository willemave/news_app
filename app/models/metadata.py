"""
Unified metadata models for content types.
Merges functionality from app/schemas/metadata.py and app/domain/content.py.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


# Enums from app/domain/content.py
class ContentType(str, Enum):
    ARTICLE = "article"
    PODCAST = "podcast"


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

    text: str = Field(..., min_length=10, max_length=1000)
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
                "full_markdown": "# AI Advances in Natural Language Processing\n\nFull article content in markdown format...",
            }
        }
    )

    title: str = Field(
        ..., min_length=10, max_length=200, description="Descriptive title for the content"
    )
    overview: str = Field(
        ..., min_length=50, max_length=2000, description="Brief overview paragraph"
    )
    bullet_points: list[SummaryBulletPoint] = Field(..., min_items=3, max_items=10)
    quotes: list[ContentQuote] = Field(default_factory=list, max_items=5)
    topics: list[str] = Field(default_factory=list, max_items=10)
    summarization_date: datetime = Field(default_factory=datetime.utcnow)
    classification: str = Field(
        default="to_read", description="Content classification: 'to_read' or 'skip'"
    )
    full_markdown: str = Field(
        default="", description="Full article content formatted as clean, readable markdown"
    )


# Base metadata with source field added
class BaseContentMetadata(BaseModel):
    """Base metadata fields common to all content types."""

    model_config = ConfigDict(extra="allow")

    # NEW: Source field to track content origin
    source: str | None = Field(
        None, description="Source of content (e.g., substack name, podcast name, subreddit name)"
    )

    summary: StructuredSummary | None = Field(None, description="AI-generated structured summary")
    summarization_date: datetime | None = None
    word_count: int | None = Field(None, ge=0)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, v):
        """Validate structured summary format."""
        if v is None:
            return None
        if isinstance(v, dict):
            return StructuredSummary(**v)
        return v


# Article metadata from app/schemas/metadata.py
class ArticleMetadata(BaseContentMetadata):
    """Metadata specific to articles."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "Import AI",
                "content": "Full article text...",
                "full_markdown": "# Full Article\n\nMarkdown formatted content...",
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
    full_markdown: str | None = Field(
        None, description="Full article content formatted as markdown"
    )

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

    id: int | None = None
    content_type: ContentType
    url: HttpUrl
    title: str | None = None
    status: ContentStatus = ContentStatus.NEW
    metadata: dict[str, Any] = Field(default_factory=dict)

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

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    @property
    def summary(self) -> str | None:
        """Get summary text (either simple or overview from structured)."""
        summary_data = self.metadata.get("summary")
        if not summary_data:
            return None
        if isinstance(summary_data, str):
            return summary_data
        if isinstance(summary_data, dict):
            return summary_data.get("overview", "")
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
        summary = self.summary
        return summary

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
    def source(self) -> str | None:
        """Get content source (substack name, podcast name, subreddit)."""
        return self.metadata.get("source")

    @property
    def full_markdown(self) -> str | None:
        """Get full article content formatted as markdown."""
        return self.metadata.get("full_markdown")


# Helper functions from app/schemas/metadata.py
def validate_content_metadata(
    content_type: str, metadata: dict
) -> ArticleMetadata | PodcastMetadata:
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

    if content_type == "article":
        return ArticleMetadata(**cleaned_metadata)
    elif content_type == "podcast":
        return PodcastMetadata(**cleaned_metadata)
    else:
        raise ValueError(f"Unknown content type: {content_type}")


def migrate_legacy_metadata(content_type: str, metadata: dict) -> dict:
    """
    Migrate legacy metadata format to new schema.

    Args:
        content_type: Type of content
        metadata: Legacy metadata dictionary

    Returns:
        Migrated metadata dictionary
    """
    # Handle legacy summary format - convert string to structured
    if "summary" in metadata and isinstance(metadata["summary"], str):
        # Convert string summary to structured format
        legacy_summary = metadata["summary"]
        metadata["summary"] = {
            "overview": legacy_summary[:500] if len(legacy_summary) > 500 else legacy_summary,
            "bullet_points": [
                {
                    "text": "Legacy summary migrated - please re-summarize for better results",
                    "category": "key_finding",
                }
            ],
            "quotes": [],
            "topics": ["Legacy"],
            "summarization_date": metadata.get("summarization_date", datetime.utcnow().isoformat()),
        }

    # Ensure datetime fields are properly formatted
    datetime_fields = ["publication_date", "summarization_date"]
    for field in datetime_fields:
        if field in metadata:
            if metadata[field] is None:
                # Remove None values
                metadata.pop(field, None)
            elif isinstance(metadata[field], str):
                try:
                    # Parse and reformat to ISO format
                    dt = datetime.fromisoformat(metadata[field].replace("Z", "+00:00"))
                    metadata[field] = dt.isoformat()
                except (ValueError, AttributeError):
                    # Remove invalid datetime
                    metadata.pop(field, None)

    return metadata
