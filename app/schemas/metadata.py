from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
                "overview": "Brief overview of the content",
                "bullet_points": [
                    {"text": "Key point 1", "category": "key_finding"},
                    {"text": "Key point 2", "category": "methodology"},
                ],
                "quotes": [{"text": "Notable quote from the content", "context": "Author Name"}],
                "topics": ["AI", "Technology", "Innovation"],
                "summarization_date": "2025-06-14T10:30:00Z",
            }
        }
    )

    overview: str = Field(
        ..., min_length=50, max_length=2000, description="Brief overview paragraph"
    )
    bullet_points: list[SummaryBulletPoint] = Field(..., min_items=3, max_items=10)
    quotes: list[ContentQuote] = Field(default_factory=list, max_items=5)
    topics: list[str] = Field(default_factory=list, max_items=10)
    summarization_date: datetime = Field(default_factory=datetime.utcnow)


class BaseContentMetadata(BaseModel):
    """Base metadata fields common to all content types."""

    model_config = ConfigDict(extra="allow")

    summary: str | StructuredSummary | None = Field(None, description="AI-generated summary")
    summarization_date: datetime | None = None
    word_count: int | None = Field(None, ge=0)

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, v):
        """Allow both string and structured summaries for backward compatibility."""
        if isinstance(v, dict) and "bullet_points" in v:
            return StructuredSummary(**v)
        return v


class ArticleMetadata(BaseContentMetadata):
    """Metadata specific to articles."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "content": "Full article text...",
                "author": "John Doe",
                "publication_date": "2025-06-14T00:00:00",
                "content_type": "html",
                "final_url_after_redirects": "https://example.com/article",
                "word_count": 1500,
                "summary": "Article summary...",
            }
        }
    )

    content: str = Field(..., min_length=1, description="Full article text content")
    author: str | None = Field(None, max_length=200)
    publication_date: datetime | None = None
    content_type: str = Field(default="html", pattern="^(pdf|html|text|markdown)$")
    final_url_after_redirects: str | None = Field(None, max_length=2000)


class PodcastMetadata(BaseContentMetadata):
    """Metadata specific to podcasts."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "audio_url": "https://example.com/episode.mp3",
                "transcript": "Full transcript text...",
                "duration": 3600,
                "episode_number": 42,
                "summary": "Podcast summary...",
            }
        }
    )

    audio_url: str = Field(..., max_length=2000, description="URL to the audio file")
    transcript: str | None = Field(None, description="Full transcript text")
    duration: int | None = Field(None, ge=0, description="Duration in seconds")
    episode_number: int | None = Field(None, ge=0)


class ProcessingError(BaseModel):
    """Error information for failed processing."""

    error: str = Field(..., description="Error message")
    error_type: str = Field(default="unknown", pattern="^(retryable|non_retryable|unknown)$")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


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
    # Handle legacy summary format
    if "summary" in metadata and isinstance(metadata["summary"], str):
        # Keep as string for now, will be converted to structured format later
        pass

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
