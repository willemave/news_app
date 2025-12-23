"""URL detection utilities for content type inference.

These utilities are used by both content_submission.py and
sequential_task_processor.py to determine content types from URLs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from app.models.metadata import ContentType

PODCAST_HOST_PLATFORMS: dict[str, str] = {
    "open.spotify.com": "spotify",
    "spotify.link": "spotify",
    "podcasts.apple.com": "apple_podcasts",
    "music.apple.com": "apple_music",
    "overcast.fm": "overcast",
    "pca.st": "pocket_casts",
    "pocketcasts.com": "pocket_casts",
    "rss.com": "rss",
    "podcasters.spotify.com": "spotify",
    "podcastaddict.com": "podcast_addict",
    "castbox.fm": "castbox",
}

PODCAST_PATH_KEYWORDS = ("podcast", "episode", "episodes", "show")

# Platforms where we skip LLM analysis and use pattern-based detection
# These are well-known platforms with predictable URL structures
PLATFORMS_SKIP_LLM_ANALYSIS = {
    "open.spotify.com",
    "spotify.link",
    "podcasts.apple.com",
    "music.apple.com",
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com",
    "overcast.fm",
    "pca.st",
    "pocketcasts.com",
}


def _normalize_platform(platform: str | None) -> str | None:
    """Lowercase and trim platform strings."""
    if not platform:
        return None
    return platform.strip().lower() or None


def infer_content_type_and_platform(
    url: str, provided_type: ContentType | None, platform_hint: str | None
) -> tuple[ContentType, str | None]:
    """Infer content type and platform based on host/path or provided hints.

    Args:
        url: Normalized URL to inspect.
        provided_type: Optional explicit content type from the client.
        platform_hint: Optional platform hint from the client.

    Returns:
        Tuple of inferred content type and normalized platform (if any).
    """
    # Import here to avoid circular imports
    from app.models.metadata import ContentType

    if provided_type:
        platform = _normalize_platform(platform_hint)
        return provided_type, platform

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    hostname = hostname[4:] if hostname.startswith("www.") else hostname
    platform = PODCAST_HOST_PLATFORMS.get(hostname)

    if platform:
        return ContentType.PODCAST, platform

    path = parsed.path.lower()
    if any(keyword in path for keyword in PODCAST_PATH_KEYWORDS):
        return ContentType.PODCAST, _normalize_platform(platform_hint)

    return ContentType.ARTICLE, _normalize_platform(platform_hint)


def should_use_llm_analysis(url: str) -> bool:
    """Determine if URL should use LLM analysis or pattern-based detection.

    For well-known platforms (Spotify, YouTube, Apple Podcasts, etc.),
    we skip the LLM call and use pattern-based detection for speed.

    Args:
        url: Normalized URL to check.

    Returns:
        True if LLM analysis should be used, False for pattern-based detection.
    """
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    # Check against known platforms that don't need LLM analysis
    if hostname in PLATFORMS_SKIP_LLM_ANALYSIS:
        return False

    # Also skip if already a known podcast platform from PODCAST_HOST_PLATFORMS
    hostname_no_www = hostname[4:] if hostname.startswith("www.") else hostname
    return hostname_no_www not in PODCAST_HOST_PLATFORMS
