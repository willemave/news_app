"""Pydantic models for API endpoints."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl

from app.constants import TWEET_SUGGESTION_MODEL
from app.models.metadata import ContentStatus, ContentType
from app.services.llm_models import LLMProvider as ChatModelProvider


class ChatMessageRole(str, Enum):
    """Role of a chat message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatSessionSummaryResponse(BaseModel):
    """Summary of a chat session for list view."""

    id: int = Field(..., description="Unique session identifier")
    content_id: int | None = Field(None, description="Associated content ID if any")
    title: str | None = Field(None, description="Session title")
    session_type: str | None = Field(
        None, description="Session type (article_brain, topic, ad_hoc)"
    )
    topic: str | None = Field(None, description="Topic if session was started from a topic")
    llm_provider: str = Field(..., description="LLM provider (openai, anthropic, google)")
    llm_model: str = Field(..., description="Full model specification (e.g., openai:gpt-5.1)")
    created_at: datetime = Field(..., description="Session creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    last_message_at: datetime | None = Field(None, description="Timestamp of last message")
    article_title: str | None = Field(None, description="Title of associated article if any")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "content_id": 123,
                "title": "Understanding AI Agents",
                "session_type": "article_brain",
                "topic": None,
                "llm_provider": "openai",
                "llm_model": "openai:gpt-5.1",
                "created_at": "2025-11-28T10:00:00Z",
                "updated_at": "2025-11-28T10:30:00Z",
                "last_message_at": "2025-11-28T10:30:00Z",
                "article_title": "How AI Agents Work",
            }
        }


class ChatMessageResponse(BaseModel):
    """A single chat message for display."""

    id: int = Field(..., description="Message ID")
    role: ChatMessageRole = Field(..., description="Message role (user/assistant/system/tool)")
    timestamp: datetime = Field(..., description="Message timestamp")
    content: str = Field(..., description="Message content")

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "role": "user",
                "timestamp": "2025-11-28T10:00:00Z",
                "content": "What are the key takeaways from this article?",
            }
        }


class ChatSessionDetailResponse(BaseModel):
    """Detailed chat session with messages."""

    session: ChatSessionSummaryResponse = Field(..., description="Session summary")
    messages: list[ChatMessageResponse] = Field(..., description="Chat messages in order")

    class Config:
        json_schema_extra = {
            "example": {
                "session": {
                    "id": 1,
                    "content_id": 123,
                    "title": "Understanding AI Agents",
                    "session_type": "article_brain",
                    "llm_provider": "openai",
                    "llm_model": "openai:gpt-5.1",
                    "created_at": "2025-11-28T10:00:00Z",
                    "updated_at": "2025-11-28T10:30:00Z",
                    "last_message_at": "2025-11-28T10:30:00Z",
                    "article_title": "How AI Agents Work",
                },
                "messages": [
                    {
                        "id": 1,
                        "role": "user",
                        "timestamp": "2025-11-28T10:00:00Z",
                        "content": "What are the key takeaways?",
                    },
                    {
                        "id": 2,
                        "role": "assistant",
                        "timestamp": "2025-11-28T10:00:05Z",
                        "content": "The key takeaways from this article are...",
                    },
                ],
            }
        }


class CreateChatSessionRequest(BaseModel):
    """Request to create a new chat session."""

    content_id: int | None = Field(None, description="Content ID to chat about")
    topic: str | None = Field(None, max_length=500, description="Specific topic to discuss")
    llm_provider: ChatModelProvider | None = Field(
        None, description="LLM provider (defaults to openai)"
    )
    llm_model_hint: str | None = Field(
        None, max_length=100, description="Optional specific model to use"
    )
    initial_message: str | None = Field(
        None, max_length=2000, description="Optional initial user message"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content_id": 123,
                "topic": None,
                "llm_provider": "openai",
                "llm_model_hint": None,
                "initial_message": "What are the key insights from this article?",
            }
        }


class UpdateChatSessionRequest(BaseModel):
    """Request to update a chat session."""

    llm_provider: ChatModelProvider | None = Field(
        None, description="New LLM provider to use for this session"
    )
    llm_model_hint: str | None = Field(
        None, max_length=100, description="Optional specific model to use"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "llm_provider": "anthropic",
                "llm_model_hint": None,
            }
        }


class CreateChatSessionResponse(BaseModel):
    """Response after creating a chat session."""

    session: ChatSessionSummaryResponse = Field(..., description="Created session")

    class Config:
        json_schema_extra = {
            "example": {
                "session": {
                    "id": 1,
                    "content_id": 123,
                    "title": "How AI Agents Work",
                    "session_type": "article_brain",
                    "llm_provider": "openai",
                    "llm_model": "openai:gpt-5.1",
                    "created_at": "2025-11-28T10:00:00Z",
                    "updated_at": None,
                    "last_message_at": None,
                    "article_title": "How AI Agents Work",
                }
            }
        }


class SendChatMessageRequest(BaseModel):
    """Request to send a message in a chat session."""

    message: str = Field(..., min_length=1, max_length=10000, description="Message to send")

    class Config:
        json_schema_extra = {"example": {"message": "Can you explain that in more detail?"}}


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
    is_aggregate: bool = Field(
        False, description="Whether this news item aggregates multiple links"
    )
    item_count: int | None = Field(
        None, description="Number of child items when content_type is news"
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
                "is_aggregate": False,
                "item_count": None,
                "image_url": "/static/images/content/123.png",
                "thumbnail_url": "/static/images/thumbnails/123.png",
            }
        }


class ContentListResponse(BaseModel):
    """Response for content list endpoint."""

    contents: list[ContentSummaryResponse] = Field(..., description="List of content items")
    total: int = Field(..., description="Total number of items")
    available_dates: list[str] = Field(..., description="List of available dates (YYYY-MM-DD)")
    content_types: list[str] = Field(..., description="Available content types for filtering")
    next_cursor: str | None = Field(
        None, description="Opaque cursor token for next page (null if no more results)"
    )
    has_more: bool = Field(False, description="Whether more results are available")
    page_size: int = Field(0, description="Number of items in current response")

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
                "total": 1,
                "available_dates": ["2025-06-19", "2025-06-18"],
                "content_types": ["article", "podcast", "news"],
                "next_cursor": "eyJsYXN0X2lkIjoxMjN9",
                "has_more": True,
                "page_size": 25,
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
    is_aggregate: bool = Field(False, description="Whether this content aggregates multiple items")
    rendered_markdown: str | None = Field(
        None, description="Rendered markdown list for legacy news aggregates"
    )
    news_items: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Legacy structured child items for news content",
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
        None, description="Detected RSS/Atom feed for this content (only for user submissions)"
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
                "is_aggregate": False,
                "rendered_markdown": None,
                "news_items": [],
                "image_url": "/static/images/content/123.png",
                "thumbnail_url": "/static/images/thumbnails/123.png",
            }
        }


class SubmitContentRequest(BaseModel):
    """Request to submit a user-provided URL for processing."""

    url: HttpUrl = Field(..., description="URL to submit (http/https only)")
    content_type: ContentType | None = Field(
        None,
        description="Content type hint. If omitted, the server will infer based on the URL.",
    )
    title: str | None = Field(
        None,
        max_length=500,
        description="Optional title supplied by the client/share sheet",
    )
    platform: str | None = Field(
        None, max_length=50, description="Optional platform hint (e.g., spotify, substack)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://open.spotify.com/episode/abc123",
                "content_type": "podcast",
                "title": "Great interview about AI",
                "platform": "spotify",
            }
        }


class ContentSubmissionResponse(BaseModel):
    """Response describing the result of a user submission."""

    content_id: int = Field(..., description="ID of the created or existing content")
    content_type: ContentType = Field(..., description="Content type that will be processed")
    status: ContentStatus = Field(..., description="Current processing status of the content")
    platform: str | None = Field(None, description="Normalized platform name if available")
    already_exists: bool = Field(
        False, description="Whether the submission matched an existing record"
    )
    message: str = Field(..., description="Human-readable status message")
    task_id: int | None = Field(None, description="Processing task ID enqueued for this content")
    source: str | None = Field(
        None, description="Source attribution recorded for the content (self submission)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content_id": 42,
                "content_type": "podcast",
                "status": "new",
                "platform": "spotify",
                "already_exists": False,
                "message": "Content queued for processing",
                "task_id": 101,
                "source": "self submission",
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
    llm_provider: str | None = Field(
        None,
        description="LLM provider to use (openai, anthropic, google). Defaults to google.",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "emphasize the startup angle",
                "creativity": 7,
                "llm_provider": "google",
            }
        }


class TweetSuggestionsResponse(BaseModel):
    """Response containing generated tweet suggestions."""

    content_id: int = Field(..., description="ID of the content these tweets are about")
    creativity: int = Field(..., description="Creativity level used for generation")
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
