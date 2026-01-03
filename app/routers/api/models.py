"""Pydantic models for API endpoints."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.constants import TWEET_SUGGESTION_MODEL
from app.models.content_submission import (  # noqa: F401
    ContentSubmissionResponse,
    SubmitContentRequest,
)
from app.models.pagination import PaginationMetadata


class ContentSummaryResponse(BaseModel):
    """Summary information for a content item in list view."""

    id: int = Field(..., description="Unique identifier")
    content_type: str = Field(..., description="Type of content (article/podcast/news)")
    url: str = Field(..., description="Original URL of the content")
    title: str | None = Field(None, description="Content title")
    source: str | None = Field(
        None, description="Content source (e.g., substack name, podcast name)"
    )
    platform: str | None = Field(
        None, description="Content platform (e.g., twitter, substack, youtube)"
    )
    status: str = Field(..., description="Processing status")
    short_summary: str | None = Field(
        None,
        description=(
            "Short summary for display; for news items this returns the excerpt or first item text"
        ),
    )
    created_at: str = Field(..., description="ISO timestamp when content was created")
    processed_at: str | None = Field(None, description="ISO timestamp when content was processed")
    classification: str | None = Field(None, description="Content classification (to_read/skip)")
    publication_date: str | None = Field(
        None, description="ISO timestamp of when content was published"
    )
    is_read: bool = Field(False, description="Whether the content has been marked as read")
    is_favorited: bool = Field(False, description="Whether the content has been favorited")
    news_article_url: str | None = Field(
        None, description="Canonical article link for news content"
    )
    news_discussion_url: str | None = Field(
        None, description="Aggregator discussion URL (HN thread, tweet, etc.)"
    )
    news_key_points: list[str] | None = Field(
        None, description="Key points provided for news digests"
    )
    news_summary: str | None = Field(
        None, description="Short overview synthesized for news digests"
    )
    user_status: str | None = Field(
        None, description="Per-user content status (e.g., inbox, archived)"
    )
    image_url: str | None = Field(
        None, description="URL of full-size AI-generated image for this content"
    )
    thumbnail_url: str | None = Field(
        None, description="URL of 200px thumbnail image for fast loading in list views"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "content_type": "article",
                "url": "https://example.com/article",
                "title": "Understanding AI in 2025",
                "source": "Tech Blog",
                "platform": "substack",
                "status": "completed",
                "short_summary": "This article explores the latest developments in AI...",
                "created_at": "2025-06-19T10:30:00Z",
                "processed_at": "2025-06-19T10:35:00Z",
                "classification": "to_read",
                "publication_date": "2025-06-18T12:00:00Z",
                "is_read": False,
                "image_url": "/static/images/content/123.png",
                "thumbnail_url": "/static/images/thumbnails/123.png",
            }
        }


class ContentListResponse(BaseModel):
    """Response for content list endpoint."""

    contents: list[ContentSummaryResponse] = Field(..., description="List of content items")
    available_dates: list[str] = Field(..., description="List of available dates (YYYY-MM-DD)")
    content_types: list[str] = Field(..., description="Available content types for filtering")
    meta: PaginationMetadata = Field(..., description="Pagination metadata for the response")

    class Config:
        json_schema_extra = {
            "example": {
                "contents": [
                    {
                        "id": 123,
                        "content_type": "article",
                        "url": "https://example.com/article",
                        "title": "Understanding AI in 2025",
                        "source": "Tech Blog",
                        "platform": "substack",
                        "status": "completed",
                        "short_summary": "This article explores...",
                        "created_at": "2025-06-19T10:30:00Z",
                        "processed_at": "2025-06-19T10:35:00Z",
                        "classification": "to_read",
                    }
                ],
                "available_dates": ["2025-06-19", "2025-06-18"],
                "content_types": ["article", "podcast", "news"],
                "meta": {
                    "next_cursor": "eyJsYXN0X2lkIjoxMjN9",
                    "has_more": True,
                    "page_size": 25,
                    "total": 1,
                },
            }
        }


class DetectedFeed(BaseModel):
    """Detected RSS/Atom feed from content page."""

    url: str = Field(..., description="Feed URL")
    type: str = Field(..., description="Feed type: substack, podcast_rss, or atom")
    title: str | None = Field(None, description="Feed title from link tag")
    format: str = Field("rss", description="Feed format: rss or atom")

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://example.substack.com/feed",
                "type": "substack",
                "title": "Example Newsletter",
                "format": "rss",
            }
        }


class ContentDetailResponse(BaseModel):
    """Detailed response for a single content item."""

    id: int = Field(..., description="Unique identifier")
    content_type: str = Field(..., description="Type of content (article/podcast/news)")
    url: str = Field(..., description="Original URL of the content")
    title: str | None = Field(None, description="Content title")
    display_title: str = Field(
        ..., description="Display title (prefers summary title over content title)"
    )
    source: str | None = Field(None, description="Content source")
    status: str = Field(..., description="Processing status")
    error_message: str | None = Field(None, description="Error message if processing failed")
    retry_count: int = Field(..., description="Number of retry attempts")
    metadata: dict[str, Any] = Field(..., description="Content-specific metadata")
    created_at: str = Field(..., description="ISO timestamp when content was created")
    updated_at: str | None = Field(None, description="ISO timestamp of last update")
    processed_at: str | None = Field(None, description="ISO timestamp when content was processed")
    checked_out_by: str | None = Field(None, description="Worker ID that checked out this content")
    checked_out_at: str | None = Field(
        None, description="ISO timestamp when content was checked out"
    )
    publication_date: str | None = Field(
        None, description="ISO timestamp of when content was published"
    )
    is_read: bool = Field(False, description="Whether the content has been marked as read")
    is_favorited: bool = Field(False, description="Whether the content has been favorited")
    # Additional useful properties from ContentData
    summary: str | None = Field(None, description="Summary text")
    short_summary: str | None = Field(None, description="Short version of summary for list view")
    structured_summary: dict[str, Any] | None = Field(
        None, description="Structured summary with bullet points and quotes"
    )
    bullet_points: list[dict[str, str]] = Field(
        ..., description="Bullet points from structured summary"
    )
    quotes: list[dict[str, str]] = Field(..., description="Quotes from structured summary")
    topics: list[str] = Field(..., description="Topics from structured summary")
    full_markdown: str | None = Field(
        None, description="Full article content formatted as markdown"
    )
    news_article_url: str | None = Field(
        None, description="Canonical article link for news content"
    )
    news_discussion_url: str | None = Field(
        None, description="Aggregator discussion URL (HN thread, tweet, etc.)"
    )
    news_key_points: list[str] | None = Field(
        None, description="Key points provided for news digests"
    )
    news_summary: str | None = Field(
        None, description="Short overview synthesized for news digests"
    )
    image_url: str | None = Field(
        None, description="URL of full-size AI-generated image for this content"
    )
    thumbnail_url: str | None = Field(
        None, description="URL of 200px thumbnail image for fast loading"
    )
    detected_feed: DetectedFeed | None = Field(
        None, description="Detected RSS/Atom feed for this content"
    )
    can_subscribe: bool = Field(
        False,
        description="Whether the current user can subscribe to the detected feed",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 123,
                "content_type": "article",
                "url": "https://example.com/article",
                "title": "Understanding AI in 2025",
                "source": "Tech Blog",
                "status": "completed",
                "error_message": None,
                "retry_count": 0,
                "metadata": {
                    "source": "Tech Blog",
                    "author": "Jane Doe",
                    "publication_date": "2025-06-19T00:00:00Z",
                    "content_type": "html",
                    "word_count": 1500,
                    "summary": {
                        "title": "Understanding AI in 2025",
                        "overview": "This article explores the latest developments...",
                        "bullet_points": [
                            {"text": "AI is transforming industries", "category": "key_finding"}
                        ],
                        "quotes": [{"text": "The future is now", "context": "Jane Doe"}],
                        "topics": ["AI", "Technology", "Future"],
                        "summarization_date": "2025-06-19T10:35:00Z",
                        "classification": "to_read",
                    },
                },
                "created_at": "2025-06-19T10:30:00Z",
                "updated_at": "2025-06-19T10:35:00Z",
                "processed_at": "2025-06-19T10:35:00Z",
                "checked_out_by": None,
                "checked_out_at": None,
                "publication_date": "2025-06-18T12:00:00Z",
                "is_read": False,
                "display_title": "Understanding AI in 2025",
                "summary": "This article explores the latest developments...",
                "short_summary": "This article explores the latest developments...",
                "structured_summary": {
                    "title": "Understanding AI in 2025",
                    "overview": "This article explores the latest developments...",
                    "bullet_points": [
                        {"text": "AI is transforming industries", "category": "key_finding"}
                    ],
                    "quotes": [{"text": "The future is now", "context": "Jane Doe"}],
                    "topics": ["AI", "Technology", "Future"],
                    "summarization_date": "2025-06-19T10:35:00Z",
                    "classification": "to_read",
                },
                "bullet_points": [
                    {"text": "AI is transforming industries", "category": "key_finding"}
                ],
                "quotes": [{"text": "The future is now", "context": "Jane Doe"}],
                "topics": ["AI", "Technology", "Future"],
                "full_markdown": "# Understanding AI in 2025\n\nFull article content...",
                "image_url": "/static/images/content/123.png",
                "thumbnail_url": "/static/images/thumbnails/123.png",
                "can_subscribe": False,
            }
        }


class BulkMarkReadRequest(BaseModel):
    """Request to mark multiple content items as read."""

    content_ids: list[int] = Field(
        ..., description="List of content IDs to mark as read", min_items=1
    )

    class Config:
        json_schema_extra = {"example": {"content_ids": [123, 456, 789]}}


class ChatGPTUrlResponse(BaseModel):
    """Response containing the ChatGPT URL for chatting with content."""

    chat_url: str = Field(..., description="URL to open ChatGPT with the content")
    truncated: bool = Field(..., description="Whether the content was truncated to fit URL limits")

    class Config:
        json_schema_extra = {
            "example": {
                "chat_url": "https://chat.openai.com/?q=Chat+about+this+article...",
                "truncated": False,
            }
        }


class UnreadCountsResponse(BaseModel):
    """Response containing unread counts by content type."""

    article: int = Field(..., description="Number of unread articles")
    podcast: int = Field(..., description="Number of unread podcasts")
    news: int = Field(..., description="Number of unread news items")


class ConvertNewsResponse(BaseModel):
    """Response for converting news link to article."""

    status: str = Field(..., description="Operation status")
    new_content_id: int = Field(..., description="ID of the article content")
    original_content_id: int = Field(..., description="ID of the original news content")
    already_exists: bool = Field(..., description="Whether article already existed")
    message: str = Field(..., description="Human-readable message")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "new_content_id": 123,
                "original_content_id": 456,
                "already_exists": False,
                "message": "Article created and queued for processing",
            }
        }


class TweetSuggestion(BaseModel):
    """A single tweet suggestion generated by the LLM."""

    id: int = Field(..., ge=1, le=3, description="Suggestion ID (1-3)")
    text: str = Field(..., description="Tweet text")
    style_label: str | None = Field(
        None, description="Style descriptor (e.g., 'insightful', 'provocative')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "text": (
                    "Great read on AI agents. Key insight: the best agents don't try "
                    "to be human, they try to be useful. https://example.com/article"
                ),
                "style_label": "insightful",
            }
        }


class TweetLength(str, Enum):
    """Tweet length preference."""

    SHORT = "short"  # 100-180 chars - concise, punchy
    MEDIUM = "medium"  # 180-280 chars - balanced
    LONG = "long"  # 280-400 chars - detailed


class TweetSuggestionsRequest(BaseModel):
    """Request body for generating tweet suggestions."""

    message: str | None = Field(
        None,
        max_length=500,
        description="Optional user guidance for tweet generation",
    )
    creativity: int = Field(
        5,
        ge=1,
        le=10,
        description="Creativity level 1-10 (1=factual, 10=bold/playful)",
    )
    length: TweetLength = Field(
        TweetLength.MEDIUM,
        description="Tweet length preference (short=100-180, medium=180-280, long=280-400 chars)",
    )
    llm_provider: str | None = Field(
        None,
        description="LLM provider to use (openai, anthropic, google). Defaults to google.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "emphasize the startup angle",
                "creativity": 7,
                "length": "medium",
                "llm_provider": "google",
            }
        }


class TweetSuggestionsResponse(BaseModel):
    """Response containing generated tweet suggestions."""

    content_id: int = Field(..., description="ID of the content these tweets are about")
    creativity: int = Field(..., description="Creativity level used for generation")
    length: TweetLength = Field(..., description="Length preference used for generation")
    model: str = Field(
        default=TWEET_SUGGESTION_MODEL,
        description="LLM model used for generation",
    )
    suggestions: list[TweetSuggestion] = Field(
        ...,
        min_length=3,
        max_length=3,
        description="Exactly 3 tweet suggestions",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content_id": 123,
                "creativity": 7,
                "model": TWEET_SUGGESTION_MODEL,
                "suggestions": [
                    {
                        "id": 1,
                        "text": (
                            "Great read on AI agents. The best agents don't try to be "
                            "human, they try to be useful. https://example.com"
                        ),
                        "style_label": "insightful",
                    },
                    {
                        "id": 2,
                        "text": (
                            "This piece nails it. We're not building artificial humans, "
                            "we're building artificial usefulness. https://example.com"
                        ),
                        "style_label": "provocative",
                    },
                    {
                        "id": 3,
                        "text": (
                            "Reading this made me rethink how we frame AI. Stop asking "
                            "'can it think?' Start asking 'can it help?' https://example.com"
                        ),
                        "style_label": "reflective",
                    },
                ],
            }
        }
