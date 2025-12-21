"""Content analysis service using OpenAI web search for type detection and media URL extraction.

Uses OpenAI's Responses API with web_search_preview tool to analyze URLs and determine:
- Content type (article, podcast, video)
- Direct media URLs (mp3/mp4) for podcasts and videos
- Platform identification
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from openai import APIConnectionError, APIError, OpenAI, RateLimitError
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

# Configuration
CONTENT_ANALYSIS_MODEL = "gpt-4o"
CONTENT_ANALYSIS_TIMEOUT = 15.0  # Slightly longer for web search


class ContentAnalysisResult(BaseModel):
    """Structured output schema for OpenAI content analysis."""

    content_type: Literal["article", "podcast", "video"] = Field(
        ...,
        description=(
            "Type of content: 'article' for web pages/blog posts/news, "
            "'podcast' for audio episodes, 'video' for video content"
        ),
    )
    original_url: str = Field(..., description="The URL that was analyzed")
    media_url: str | None = Field(
        None,
        description=(
            "Direct URL to media file (mp3/mp4/m4a/webm) for podcasts/videos. "
            "Extract from page HTML if available. Look for audio/video source tags, "
            "RSS feed enclosures, or download links."
        ),
    )
    media_format: str | None = Field(
        None,
        description="Media file format/extension: mp3, mp4, m4a, webm, etc.",
    )
    title: str | None = Field(None, description="Content title if detectable from the page")
    description: str | None = Field(None, description="Brief description or subtitle if available")
    duration_seconds: int | None = Field(
        None, description="Duration in seconds for audio/video content if mentioned"
    )
    platform: str | None = Field(
        None,
        description=(
            "Platform name in lowercase: spotify, apple_podcasts, youtube, "
            "substack, medium, transistor, anchor, simplecast, etc."
        ),
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for the content type detection (0.0-1.0)",
    )


@dataclass
class AnalysisError:
    """Error from content analysis."""

    message: str
    recoverable: bool = True


class ContentAnalyzer:
    """Analyzes URLs to determine content type and extract media URLs.

    Uses OpenAI's Responses API with web_search_preview tool to fetch
    and analyze web pages, extracting structured information about
    the content type and any available media URLs.
    """

    def __init__(self) -> None:
        """Initialize the content analyzer."""
        self._settings = get_settings()
        self._client: OpenAI | None = None

    def _get_client(self) -> OpenAI:
        """Get or create the synchronous OpenAI client."""
        if self._client is None:
            if not self._settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self._client = OpenAI(
                api_key=self._settings.openai_api_key,
                timeout=CONTENT_ANALYSIS_TIMEOUT,
            )
        return self._client

    def analyze_url(self, url: str) -> ContentAnalysisResult | AnalysisError:
        """Analyze a URL to determine content type and extract media URL.

        Uses OpenAI's web search tool to fetch and analyze the page content.

        Args:
            url: The URL to analyze.

        Returns:
            ContentAnalysisResult on success, AnalysisError on failure.
        """
        try:
            client = self._get_client()

            logger.info(
                "Starting content analysis for URL",
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {"url": url},
                },
            )

            # Build the JSON schema for structured output
            schema = ContentAnalysisResult.model_json_schema()

            # Use Responses API with web_search_preview tool
            response = client.responses.create(
                model=CONTENT_ANALYSIS_MODEL,
                input=self._build_analysis_prompt(url),
                tools=[{"type": "web_search_preview"}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "content_analysis",
                        "schema": schema,
                        "strict": True,
                    }
                },
            )

            # Extract structured output
            output_text = self._extract_output_text(response)
            if not output_text:
                logger.warning(
                    "No output from content analysis",
                    extra={
                        "component": "content_analyzer",
                        "operation": "analyze_url",
                        "context_data": {"url": url},
                    },
                )
                return AnalysisError("No output from content analysis")

            # Parse JSON response into Pydantic model
            result = ContentAnalysisResult.model_validate_json(output_text)

            logger.info(
                "Content analysis complete: type=%s, has_media_url=%s, platform=%s",
                result.content_type,
                result.media_url is not None,
                result.platform,
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {
                        "url": url,
                        "content_type": result.content_type,
                        "has_media_url": result.media_url is not None,
                        "platform": result.platform,
                    },
                },
            )
            return result

        except RateLimitError as e:
            logger.warning(
                "Rate limit hit during content analysis: %s",
                e,
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {"url": url, "error": str(e)},
                },
            )
            return AnalysisError(f"Rate limit: {e}", recoverable=True)

        except APIConnectionError as e:
            logger.warning(
                "Connection error during content analysis: %s",
                e,
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {"url": url, "error": str(e)},
                },
            )
            return AnalysisError(f"Connection error: {e}", recoverable=True)

        except APIError as e:
            logger.warning(
                "API error during content analysis: status=%s, message=%s",
                e.status_code,
                str(e),
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {"url": url, "status_code": e.status_code, "error": str(e)},
                },
            )
            return AnalysisError(f"API error: {e}", recoverable=True)

        except Exception as e:
            logger.exception(
                "Unexpected error during content analysis: %s",
                e,
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {"url": url, "error": str(e)},
                },
            )
            return AnalysisError(str(e), recoverable=True)

    def _build_analysis_prompt(self, url: str) -> str:
        """Build the analysis prompt for OpenAI."""
        return f"""Analyze this URL and determine what type of content it is:

URL: {url}

Instructions:
1. Use web search to access and analyze the page content at this URL
2. Determine if this is an article, podcast episode, or video
3. For podcasts and videos, look for the direct media file URL:
   - Check for <audio> or <video> source tags
   - Look for RSS feed enclosure URLs
   - Find download links or embedded player source URLs
   - The media_url should end in .mp3, .mp4, .m4a, .webm, or similar
4. Extract the title and description if visible on the page
5. Identify the platform (spotify, youtube, substack, medium, etc.)
6. For duration, look for timestamps like "45:23" or "45 minutes"

Important:
- If this is clearly an article/blog post, set content_type to "article"
- If this is an audio podcast episode, set content_type to "podcast"
- If this is a video (YouTube, Vimeo, etc.), set content_type to "video"
- Only include media_url if you find an actual direct file URL
- Set confidence based on how certain you are about the content type

Return your analysis as structured JSON."""

    def _extract_output_text(self, response: Any) -> str | None:
        """Extract text output from OpenAI response.

        The Responses API can return output in different formats depending
        on the response structure.
        """
        # Try output_text property first (most common)
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text

        # Try parsing output items for message content
        if hasattr(response, "output") and response.output:
            for item in response.output:
                if hasattr(item, "type") and item.type == "message" and hasattr(item, "content"):
                    for content_item in item.content:
                        if hasattr(content_item, "type"):
                            if content_item.type == "output_text":
                                return getattr(content_item, "text", None)
                            if content_item.type == "text":
                                return getattr(content_item, "text", None)
        return None


# Global instance for singleton pattern
_content_analyzer: ContentAnalyzer | None = None


def get_content_analyzer() -> ContentAnalyzer:
    """Get the global content analyzer instance."""
    global _content_analyzer
    if _content_analyzer is None:
        _content_analyzer = ContentAnalyzer()
    return _content_analyzer
