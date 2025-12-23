"""Content analysis service using pydantic-ai with web search for type detection.

Uses pydantic-ai Agent with OpenAI Responses API and WebSearchTool to analyze URLs
and determine content type (article, podcast, video), extract media URLs, and
identify platforms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent, WebSearchTool
from pydantic_ai.exceptions import UnexpectedModelBehavior

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

# Configuration
CONTENT_ANALYSIS_MODEL = "openai-responses:gpt-5-mini"


class ContentAnalysisResult(BaseModel):
    """Structured output schema for content analysis."""

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


# System prompt for the content analyzer agent
CONTENT_ANALYZER_SYSTEM_PROMPT = """\
You are a content type analyzer. Your job is to analyze URLs and determine:
1. What type of content it is (article, podcast episode, or video)
2. Extract any direct media file URLs for podcasts/videos
3. Identify the platform (spotify, youtube, substack, etc.)
4. Extract title, description, and duration when available

Guidelines:
- Use web search to access and analyze the page content
- For podcasts/videos, look for direct media URLs (.mp3, .mp4, .m4a, .webm)
- Check <audio>/<video> tags, RSS enclosures, download links, embedded players
- If clearly a blog post or news article, set content_type to "article"
- If audio podcast episode, set content_type to "podcast"
- If video (YouTube, Vimeo, etc.), set content_type to "video"
- Only include media_url if you find an actual direct file URL
- Set confidence based on how certain you are about the content type"""


class ContentAnalyzer:
    """Analyzes URLs to determine content type and extract media URLs.

    Uses pydantic-ai Agent with OpenAI Responses API and WebSearchTool
    to fetch and analyze web pages, extracting structured information about
    the content type and any available media URLs.
    """

    def __init__(self) -> None:
        """Initialize the content analyzer."""
        self._settings = get_settings()
        self._agent: Agent[None, ContentAnalysisResult] | None = None

    def _get_agent(self) -> Agent[None, ContentAnalysisResult]:
        """Get or create the pydantic-ai Agent."""
        if self._agent is None:
            if not self._settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY not configured")

            self._agent = Agent(
                CONTENT_ANALYSIS_MODEL,
                output_type=ContentAnalysisResult,
                system_prompt=CONTENT_ANALYZER_SYSTEM_PROMPT,
                builtin_tools=[WebSearchTool()],
            )
        return self._agent

    def analyze_url(self, url: str) -> ContentAnalysisResult | AnalysisError:
        """Analyze a URL to determine content type and extract media URL.

        Uses pydantic-ai Agent with WebSearchTool to fetch and analyze the page.

        Args:
            url: The URL to analyze.

        Returns:
            ContentAnalysisResult on success, AnalysisError on failure.
        """
        try:
            agent = self._get_agent()

            logger.info(
                "Starting content analysis for URL",
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {"url": url, "model": CONTENT_ANALYSIS_MODEL},
                },
            )

            prompt = f"""Analyze this URL and determine what type of content it is:

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

Return your analysis."""

            result = agent.run_sync(prompt)

            logger.info(
                "Content analysis complete: type=%s, has_media_url=%s, platform=%s",
                result.output.content_type,
                result.output.media_url is not None,
                result.output.platform,
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {
                        "url": url,
                        "content_type": result.output.content_type,
                        "has_media_url": result.output.media_url is not None,
                        "platform": result.output.platform,
                    },
                },
            )
            return result.output

        except UnexpectedModelBehavior as e:
            logger.warning(
                "Model behavior error during content analysis: %s",
                e,
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {"url": url, "error": str(e)},
                },
            )
            return AnalysisError(f"Model error: {e}", recoverable=True)

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


# Global instance for singleton pattern
_content_analyzer: ContentAnalyzer | None = None


def get_content_analyzer() -> ContentAnalyzer:
    """Get the global content analyzer instance."""
    global _content_analyzer
    if _content_analyzer is None:
        _content_analyzer = ContentAnalyzer()
    return _content_analyzer
