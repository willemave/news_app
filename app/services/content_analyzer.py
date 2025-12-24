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
    (r'open\.spotify\.com/episode/([a-zA-Z0-9]+)', 'spotify'),
    (r'podcasts\.apple\.com/.+/podcast/.+/id(\d+)', 'apple_podcasts'),
    (r'music\.apple\.com/.+/album/.+/(\d+)', 'apple_music'),
    (r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', 'youtube'),
    (r'youtu\.be/([a-zA-Z0-9_-]+)', 'youtube'),
    (r'overcast\.fm/\+([a-zA-Z0-9]+)', 'overcast'),
    (r'player\.vimeo\.com/video/(\d+)', 'vimeo'),
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
You are a content type analyzer. Analyze the provided page content to determine:
1. Content type: article, podcast, or video
2. Platform links (Spotify, Apple Podcasts, YouTube, etc.)
3. Title and description

CRITICAL RULES - PRIORITY ORDER:
1. If page contains ANY podcast links (Spotify, Apple Podcasts, Overcast, etc.) \
→ classify as "podcast" and use the podcast link as media_url
2. If page contains video links (YouTube, Vimeo) → classify as "video"
3. Only classify as "article" if there are NO podcast/video links

SUBSTACK PRIORITY: Substack posts often embed podcast episodes. If you see both \
substack.com AND a podcast platform link → ALWAYS classify as "podcast" and \
set platform to the podcast platform (spotify, apple_podcasts, etc.), NOT substack."""


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

            # Step 3: If we found podcast/video platforms, we can classify quickly
            if detected["platforms"]:
                # Prioritize podcast platforms over video platforms
                video_only = ("youtube", "vimeo")
                podcast_platforms = [p for p in detected["platforms"] if p not in video_only]
                video_platforms = [p for p in detected["platforms"] if p in video_only]

                # Prefer podcast if available, otherwise video
                if podcast_platforms:
                    platform = podcast_platforms[0]
                    content_type: Literal["article", "podcast", "video"] = "podcast"
                else:
                    platform = video_platforms[0]
                    content_type = "video"

                # Find media URL for the selected platform
                media_url = None
                for url in detected["platform_urls"]:
                    url_lower = url.lower()
                    if platform in url_lower or (platform == "spotify" and "spotify" in url_lower):
                        media_url = url
                        break
                if not media_url and detected["platform_urls"]:
                    media_url = detected["platform_urls"][0]
                if not media_url and detected["audio_urls"]:
                    media_url = detected["audio_urls"][0]

                # Extract title from text (first line often)
                title = text.split("\n")[0][:200] if text else None

                logger.info(
                    "Fast-path detection: found %s links, classifying as %s",
                    detected["platforms"],
                    content_type,
                    extra={
                        "component": "content_analyzer",
                        "operation": "analyze_url",
                        "context_data": {
                            "url": url,
                            "platforms": detected["platforms"],
                            "content_type": content_type,
                        },
                    },
                )

                return ContentAnalysisResult(
                    content_type=content_type,
                    original_url=url,
                    media_url=media_url,
                    media_format="mp3" if content_type == "podcast" else "mp4",
                    title=title,
                    platform=platform,
                    confidence=0.95,
                )

            # Step 4: No obvious media links - use LLM to analyze content
            agent = self._get_agent()

            # Truncate text for LLM context
            text_snippet = (text or "")[:8000]

            prompt = f"""Analyze this page content and determine content type:

URL: {url}

DETECTED MEDIA (from HTML scan):
- Podcast/Video platforms found: {detected['platforms'] or 'None'}
- Platform URLs: {detected['platform_urls'][:2] or 'None'}
- Audio file URLs: {detected['audio_urls'][:2] or 'None'}

PAGE TEXT (first 8000 chars):
{text_snippet}

Based on the above, determine:
1. Is this an article, podcast, or video?
2. What platform is it from?
3. What is the title?

REMEMBER: If ANY podcast/video platform links were detected, classify accordingly."""

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
