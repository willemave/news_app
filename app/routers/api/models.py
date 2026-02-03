"""Pydantic models for API endpoints."""

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

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
    url: str = Field(..., description="Canonical URL of the content")
    source_url: str | None = Field(None, description="Original scraped/submitted URL")
    discussion_url: str | None = Field(
        None, description="Discussion URL (tweet, HN thread, etc.) when available"
    )
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


class SubmissionStatusResponse(BaseModel):
    """Status information for a user-submitted content item."""

    id: int = Field(..., description="Unique identifier")
    content_type: str = Field(..., description="Type of content (article/podcast/news/unknown)")
    url: str = Field(..., description="Canonical URL of the content")
    source_url: str | None = Field(None, description="Original submitted URL")
    title: str | None = Field(None, description="Content title (if detected)")
    status: str = Field(..., description="Processing status")
    error_message: str | None = Field(None, description="Failure reason when status=failed/skipped")
    created_at: str = Field(..., description="ISO timestamp when content was created")
    processed_at: str | None = Field(None, description="ISO timestamp when content was processed")
    submitted_via: str | None = Field(None, description="Submission channel (share_sheet, etc.)")
    is_self_submission: bool = Field(
        True, description="Whether this content was submitted by the current user"
    )


class SubmissionStatusListResponse(BaseModel):
    """Response for user submission status list."""

    submissions: list[SubmissionStatusResponse] = Field(
        ..., description="List of user-submitted items still processing or failed"
    )
    meta: PaginationMetadata = Field(..., description="Pagination metadata for the response")


class DownloadMoreRequest(BaseModel):
    """Request to download older items from the same feed series."""

    count: int = Field(
        ...,
        ge=1,
        le=50,
        description="Number of additional older items to attempt to fetch",
    )


class DownloadMoreResponse(BaseModel):
    """Response for the download-more action."""

    status: str = Field(..., description="Completion status")
    requested_count: int = Field(..., ge=1, le=50)
    base_limit: int = Field(..., ge=1)
    target_limit: int = Field(..., ge=1)
    scraped: int = Field(..., ge=0)
    saved: int = Field(..., ge=0)
    duplicates: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)


class DiscoverySuggestionResponse(BaseModel):
    """Suggested feed/podcast/YouTube subscription item."""

    id: int
    suggestion_type: str
    site_url: str | None = None
    feed_url: str
    item_url: str | None = None
    title: str | None = None
    description: str | None = None
    channel_id: str | None = None
    playlist_id: str | None = None
    rationale: str | None = None
    score: float | None = None
    status: str
    created_at: str


class DiscoverySuggestionsResponse(BaseModel):
    """Grouped discovery suggestions for the latest run."""

    run_id: int | None = None
    run_status: str | None = None
    run_created_at: str | None = None
    direction_summary: str | None = None
    feeds: list[DiscoverySuggestionResponse] = Field(default_factory=list)
    podcasts: list[DiscoverySuggestionResponse] = Field(default_factory=list)
    youtube: list[DiscoverySuggestionResponse] = Field(default_factory=list)


class DiscoveryRunSuggestions(BaseModel):
    """Discovery suggestions grouped by run."""

    run_id: int
    run_status: str
    run_created_at: str
    direction_summary: str | None = None
    feeds: list[DiscoverySuggestionResponse] = Field(default_factory=list)
    podcasts: list[DiscoverySuggestionResponse] = Field(default_factory=list)
    youtube: list[DiscoverySuggestionResponse] = Field(default_factory=list)


class DiscoveryHistoryResponse(BaseModel):
    """Discovery suggestions across multiple runs."""

    runs: list[DiscoveryRunSuggestions] = Field(default_factory=list)


class DiscoveryRefreshResponse(BaseModel):
    """Response for manual discovery refresh."""

    status: str
    task_id: int | None = None


class DiscoverySubscribeRequest(BaseModel):
    """Request to subscribe to discovery suggestions."""

    suggestion_ids: list[int] = Field(..., min_length=1)


class DiscoverySubscribeResponse(BaseModel):
    """Response for discovery subscription action."""

    subscribed: list[int] = Field(default_factory=list)
    skipped: list[int] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


class DiscoveryAddItemRequest(BaseModel):
    """Request to add single items from discovery suggestions."""

    suggestion_ids: list[int] = Field(..., min_length=1)


class DiscoveryAddItemResponse(BaseModel):
    """Response for adding items from discovery suggestions."""

    created: list[int] = Field(default_factory=list)
    skipped: list[int] = Field(default_factory=list)
    errors: list[dict[str, str]] = Field(default_factory=list)


class DiscoveryDismissRequest(BaseModel):
    """Request to dismiss discovery suggestions."""

    suggestion_ids: list[int] = Field(..., min_length=1)


class DiscoveryDismissResponse(BaseModel):
    """Response for discovery dismissal action."""

    dismissed: list[int] = Field(default_factory=list)


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
    url: str = Field(..., description="Canonical URL of the content")
    source_url: str | None = Field(None, description="Original scraped/submitted URL")
    discussion_url: str | None = Field(
        None, description="Discussion URL (tweet, HN thread, etc.) when available"
    )
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
    summary_kind: str | None = Field(
        None, description="Summary kind discriminator (e.g., long_interleaved)"
    )
    summary_version: int | None = Field(
        None, description="Summary schema version for the current summary kind"
    )
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


class ProcessingCountResponse(BaseModel):
    """Response containing the long-form processing count."""

    processing_count: int = Field(
        ...,
        description="Number of long-form items pending or processing for the user",
    )


class LongFormStatsResponse(BaseModel):
    """Response containing long-form content stats for a user."""

    total_count: int = Field(..., description="Total long-form items in the inbox")
    unread_count: int = Field(..., description="Unread long-form items")
    read_count: int = Field(..., description="Read long-form items")
    favorited_count: int = Field(..., description="Favorited long-form items")
    processing_count: int = Field(
        ..., description="Long-form items pending or processing for the user"
    )


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


class OnboardingProfileRequest(BaseModel):
    """Request to build a profile for onboarding personalization."""

    first_name: str = Field(..., min_length=1, max_length=120)
    interest_topics: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_interest_topics(self) -> "OnboardingProfileRequest":
        cleaned: list[str] = []
        seen: set[str] = set()
        for topic in self.interest_topics:
            if not isinstance(topic, str):
                continue
            normalized = topic.strip().strip(".,;:")
            if not normalized:
                continue
            key = normalized.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
        if not cleaned:
            raise ValueError("interest_topics is required")
        self.interest_topics = cleaned
        return self


class OnboardingProfileResponse(BaseModel):
    """Profile summary for onboarding personalization."""

    profile_summary: str
    inferred_topics: list[str] = Field(default_factory=list)
    candidate_sources: list[str] = Field(default_factory=list)


class OnboardingVoiceParseRequest(BaseModel):
    """Request to parse onboarding voice transcript into fields."""

    transcript: str = Field(..., min_length=3, max_length=6000)
    locale: str | None = Field(None, max_length=20)


class OnboardingVoiceParseResponse(BaseModel):
    """Parsed onboarding voice fields."""

    first_name: str | None = None
    interest_topics: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    missing_fields: list[str] = Field(default_factory=list)


class OnboardingAudioDiscoverRequest(BaseModel):
    """Request to start onboarding audio discovery."""

    transcript: str = Field(..., min_length=3, max_length=8000)
    locale: str | None = Field(None, max_length=20)


class OnboardingDiscoveryLaneStatus(BaseModel):
    """Status for a single onboarding discovery lane."""

    name: str
    status: str
    completed_queries: int = 0
    query_count: int = 0


class OnboardingAudioDiscoverResponse(BaseModel):
    """Response for onboarding audio discovery start."""

    run_id: int
    run_status: str
    topic_summary: str | None = None
    inferred_topics: list[str] = Field(default_factory=list)
    lanes: list[OnboardingDiscoveryLaneStatus] = Field(default_factory=list)


class RealtimeTokenResponse(BaseModel):
    """Ephemeral token for OpenAI Realtime sessions."""

    token: str
    expires_at: int | None = None
    model: str | None = None
    session_type: Literal["realtime", "transcription"] | None = None


class OnboardingSuggestion(BaseModel):
    """Single onboarding recommendation item."""

    suggestion_type: Literal["substack", "atom", "podcast_rss", "reddit"]
    title: str | None = None
    site_url: str | None = None
    feed_url: str | None = None
    subreddit: str | None = None
    rationale: str | None = None
    score: float | None = None
    is_default: bool = False


class OnboardingFastDiscoverRequest(BaseModel):
    """Request for fast onboarding discovery."""

    profile_summary: str = Field(..., min_length=3)
    inferred_topics: list[str] = Field(default_factory=list, max_length=12)


class OnboardingFastDiscoverResponse(BaseModel):
    """Response for fast onboarding discovery."""

    recommended_pods: list[OnboardingSuggestion] = Field(default_factory=list)
    recommended_substacks: list[OnboardingSuggestion] = Field(default_factory=list)
    recommended_subreddits: list[OnboardingSuggestion] = Field(default_factory=list)


class OnboardingDiscoveryStatusResponse(BaseModel):
    """Status response for onboarding audio discovery polling."""

    run_id: int
    run_status: str
    topic_summary: str | None = None
    inferred_topics: list[str] = Field(default_factory=list)
    lanes: list[OnboardingDiscoveryLaneStatus] = Field(default_factory=list)
    suggestions: OnboardingFastDiscoverResponse | None = None
    error_message: str | None = None


class OnboardingSelectedSource(BaseModel):
    """Selected source for onboarding completion."""

    suggestion_type: Literal["substack", "atom", "podcast_rss"]
    title: str | None = None
    feed_url: str = Field(..., min_length=5, max_length=2048)
    config: dict[str, Any] | None = None


class OnboardingCompleteRequest(BaseModel):
    """Request to finalize onboarding selections."""

    selected_sources: list[OnboardingSelectedSource] = Field(default_factory=list)
    selected_subreddits: list[str] = Field(default_factory=list)
    profile_summary: str | None = None
    inferred_topics: list[str] | None = None


class OnboardingCompleteResponse(BaseModel):
    """Response for onboarding completion."""

    status: str
    task_id: int | None = None
    inbox_count_estimate: int
    longform_status: str
    has_completed_new_user_tutorial: bool


class OnboardingTutorialResponse(BaseModel):
    """Response for tutorial completion."""

    has_completed_new_user_tutorial: bool
