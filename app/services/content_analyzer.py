"""Content analysis service using page fetching and LLM analysis.

Fetches actual page content using trafilatura, then uses an LLM to analyze
the HTML for embedded podcast/video links and determine content type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

import feedparser
import httpx
import trafilatura
from pydantic import BaseModel, Field
from pydantic_ai import Agent

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.feed_detection import extract_feed_links

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
1. LONG ARTICLE OVERRIDE: If page text is >3000 words AND contains a podcast embed, \
classify as "article" - the text likely contains the podcast transcript already.
2. PODCAST: If podcast platform link detected (Spotify, Apple Podcasts, Overcast) \
AND text is short (<3000 words) → content_type="podcast", platform=the podcast platform
3. VIDEO: If YouTube/Vimeo link detected (and no podcast links) → content_type="video"
4. ARTICLE: If NO podcast or video links detected, OR text is long enough to be a transcript

CRITICAL - media_url rules:
- NEVER use Spotify, Apple Podcasts, or Overcast URLs as media_url - these are NOT \
directly downloadable audio files!
- ONLY use direct audio file URLs (.mp3, .m4a, .wav, .ogg) as media_url
- If an "RSS audio URL" is provided, use that as media_url (it's a direct mp3 link)
- If only platform links exist (no direct audio), set media_url to null
- Always set platform to the detected platform name (spotify, apple_podcasts, etc.)

Newsletter/Substack posts that embed podcast episodes: if short text, classify as \
"podcast"; if long text (likely includes transcript), classify as "article"."""


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


def _detect_media_in_html(html: str, page_url: str) -> dict:
    """Scan HTML for podcast/video platform links, audio files, and RSS feeds.

    Args:
        html: Raw HTML content of the page.
        page_url: URL of the page (needed to resolve relative feed URLs).

    Returns:
        Dict with detected platforms, media URLs, and RSS feeds.
    """
    detected = {
        "platforms": [],
        "platform_urls": [],
        "audio_urls": [],
        "rss_feeds": [],
        "rss_audio_url": None,
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

    # Detect RSS feeds and try to extract audio URL
    try:
        feeds = extract_feed_links(html, page_url)
        detected["rss_feeds"] = [f["feed_url"] for f in feeds]

        # If Spotify/Apple detected but no direct audio, try RSS for audio URL
        has_platform_embed = any(
            p in detected["platforms"] for p in ("spotify", "apple_podcasts", "overcast")
        )
        if has_platform_embed and not detected["audio_urls"]:
            for feed_url in detected["rss_feeds"][:2]:  # Try first 2 feeds
                audio_url = _extract_audio_from_rss(feed_url)
                if audio_url:
                    detected["rss_audio_url"] = audio_url
                    logger.info(f"Extracted audio URL from RSS feed: {audio_url[:80]}...")
                    break
    except Exception as e:
        logger.debug(f"RSS feed detection failed: {e}")

    return detected


def _extract_audio_from_rss(feed_url: str) -> str | None:
    """Parse RSS feed and extract first audio enclosure URL.

    Args:
        feed_url: URL of the RSS feed to parse.

    Returns:
        First audio URL found, or None if no audio enclosures.
    """
    try:
        feed = feedparser.parse(feed_url)

        # Skip if parsing failed completely
        if feed.bozo and not feed.entries:
            logger.debug(f"Failed to parse RSS feed: {feed_url}")
            return None

        # Check first 5 entries for audio enclosures
        for entry in feed.entries[:5]:
            # Check enclosures for audio
            for enc in getattr(entry, "enclosures", []):
                enc_type = enc.get("type", "")
                if "audio" in enc_type:
                    return enc.get("href")

            # Check links for audio
            for link in getattr(entry, "links", []):
                link_type = link.get("type", "")
                if "audio" in link_type:
                    return link.get("href")

        return None

    except Exception as e:
        logger.debug(f"Error parsing RSS feed {feed_url}: {e}")
        return None


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

            # Step 2: Scan HTML for podcast/video links and RSS feeds
            detected = _detect_media_in_html(html, url)

            # Step 3: Use LLM to analyze content with detected media info
            agent = self._get_agent()

            # Truncate text for LLM context and calculate word count
            text_snippet = (text or "")[:6000]
            word_count = len((text or "").split())

            # Build RSS audio info for prompt
            rss_audio_info = detected.get("rss_audio_url")
            rss_audio_line = (
                f"- RSS audio URL (direct mp3): {rss_audio_info}"
                if rss_audio_info
                else "- RSS audio URL: None"
            )

            prompt = f"""Analyze this page and classify its content type.

URL: {url}
WORD COUNT: {word_count} words

DETECTED MEDIA LINKS (extracted from HTML):
- Platforms found: {detected["platforms"] or "None"}
- Platform URLs (NOT directly downloadable): {detected["platform_urls"][:3] or "None"}
- Direct audio files: {detected["audio_urls"][:2] or "None"}
{rss_audio_line}

PAGE CONTENT:
{text_snippet}

Return your classification. Remember:
- If word count > 3000 with podcast embed, classify as "article" (text likely has transcript)
- NEVER use Spotify/Apple Podcasts URLs as media_url
- Use direct audio files or RSS audio URL as media_url if available"""

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
