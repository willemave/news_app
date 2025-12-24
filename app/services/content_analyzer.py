"""Content analysis service using page fetching and LLM analysis.

Fetches actual page content using trafilatura, then uses an LLM to analyze
the HTML for embedded podcast/video links and determine content type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import httpx
import trafilatura
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

# Configuration - use standard chat model, not responses API
CONTENT_ANALYSIS_MODEL = "openai:gpt-4o-mini"

# Patterns to detect podcast/video platform links in HTML
PODCAST_VIDEO_PATTERNS = [
    (r"open\.spotify\.com/episode/([a-zA-Z0-9]+)", "spotify"),
    (r"podcasts\.apple\.com/.+/podcast/.+/id(\d+)", "apple_podcasts"),
    (r"music\.apple\.com/.+/album/.+/(\d+)", "apple_music"),
    (r"youtube\.com/watch\?v=([a-zA-Z0-9_-]+)", "youtube"),
    (r"youtu\.be/([a-zA-Z0-9_-]+)", "youtube"),
    (r"overcast\.fm/\+([a-zA-Z0-9]+)", "overcast"),
    (r"player\.vimeo\.com/video/(\d+)", "vimeo"),
]

# Audio file patterns
AUDIO_FILE_PATTERNS = [
    r'(https?://[^\s"\'<>]+\.mp3(?:\?[^\s"\'<>]*)?)',
    r'(https?://[^\s"\'<>]+\.m4a(?:\?[^\s"\'<>]*)?)',
    r'(https?://[^\s"\'<>]+\.wav(?:\?[^\s"\'<>]*)?)',
    r'(https?://[^\s"\'<>]+\.ogg(?:\?[^\s"\'<>]*)?)',
]


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
You classify web pages as article, podcast, or video.

CLASSIFICATION RULES (in priority order):
1. PODCAST: If ANY podcast platform link detected (Spotify, Apple Podcasts, Overcast) \
→ content_type="podcast", platform=the podcast platform, media_url=the podcast link
2. VIDEO: If YouTube/Vimeo link detected (and no podcast links) → content_type="video"
3. ARTICLE: Only if NO podcast or video links detected

IMPORTANT: Newsletter/Substack posts that embed podcast episodes should be \
classified as "podcast" with the podcast platform (not "substack").

Always set media_url to the detected platform URL when available."""


def _fetch_page_content(url: str) -> tuple[str | None, str | None]:
    """Fetch page HTML and extract text content.

    Returns:
        Tuple of (raw_html, extracted_text). Either may be None on failure.
    """
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as client:
            response = client.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
            response.raise_for_status()
            html = response.text
            # Extract readable text using trafilatura
            text = trafilatura.extract(html, include_links=True) or ""
            return html, text
    except Exception as e:
        logger.warning(f"Failed to fetch page content: {e}")
        return None, None


def _detect_media_in_html(html: str) -> dict:
    """Scan HTML for podcast/video platform links and audio files.

    Returns:
        Dict with detected platforms and media URLs.
    """
    detected = {
        "platforms": [],
        "platform_urls": [],
        "audio_urls": [],
    }

    # Check for podcast/video platform links
    for pattern, platform in PODCAST_VIDEO_PATTERNS:
        # Extract full URLs containing the pattern
        url_pattern = rf'(https?://[^\s"\'<>]*?{pattern.split("(")[0]}[^\s"\'<>]*)'
        urls = re.findall(url_pattern, html, re.IGNORECASE)
        if urls:
            detected["platforms"].append(platform)
            detected["platform_urls"].extend(urls[:3])  # Limit to 3

    # Check for direct audio files
    for pattern in AUDIO_FILE_PATTERNS:
        matches = re.findall(pattern, html, re.IGNORECASE)
        detected["audio_urls"].extend(matches[:3])

    # Deduplicate
    detected["platforms"] = list(set(detected["platforms"]))
    detected["platform_urls"] = list(set(detected["platform_urls"]))
    detected["audio_urls"] = list(set(detected["audio_urls"]))

    return detected


class ContentAnalyzer:
    """Analyzes URLs to determine content type and extract media URLs.

    Fetches actual page content, scans for podcast/video links, then uses
    an LLM to analyze and classify the content.
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
            )
        return self._agent

    def analyze_url(self, url: str) -> ContentAnalysisResult | AnalysisError:
        """Analyze a URL to determine content type and extract media URL.

        Fetches the page, scans for media links, then uses LLM to analyze.

        Args:
            url: The URL to analyze.

        Returns:
            ContentAnalysisResult on success, AnalysisError on failure.
        """
        try:
            logger.info(
                "Starting content analysis for URL",
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {"url": url, "model": CONTENT_ANALYSIS_MODEL},
                },
            )

            # Step 1: Fetch the actual page content
            html, text = _fetch_page_content(url)
            if not html:
                return AnalysisError("Failed to fetch page content", recoverable=True)

            # Step 2: Scan HTML for podcast/video links
            detected = _detect_media_in_html(html)

            # Step 3: Use LLM to analyze content with detected media info
            agent = self._get_agent()

            # Truncate text for LLM context
            text_snippet = (text or "")[:6000]

            prompt = f"""Analyze this page and classify its content type.

URL: {url}

DETECTED MEDIA LINKS (extracted from HTML):
- Platforms found: {detected["platforms"] or "None"}
- Platform URLs: {detected["platform_urls"][:3] or "None"}
- Direct audio files: {detected["audio_urls"][:2] or "None"}

PAGE CONTENT:
{text_snippet}

Return your classification. Use the first detected platform URL as media_url if available."""

            result = agent.run_sync(prompt)

            logger.info(
                "LLM analysis complete: type=%s, platform=%s",
                result.output.content_type,
                result.output.platform,
                extra={
                    "component": "content_analyzer",
                    "operation": "analyze_url",
                    "context_data": {
                        "url": url,
                        "content_type": result.output.content_type,
                        "platform": result.output.platform,
                    },
                },
            )
            return result.output

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
