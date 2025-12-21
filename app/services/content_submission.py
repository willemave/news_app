"""Helpers for user-submitted one-off content."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from pydantic import HttpUrl, TypeAdapter
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.constants import SELF_SUBMISSION_SOURCE
from app.core.logging import get_logger
from app.models.metadata import ContentClassification, ContentStatus, ContentType
from app.models.schema import Content, ProcessingTask
from app.models.user import User
from app.routers.api.models import ContentSubmissionResponse, SubmitContentRequest
from app.services.content_analyzer import (
    AnalysisError,
    get_content_analyzer,
)
from app.services.queue import TaskStatus, TaskType
from app.services.scraper_configs import ensure_inbox_status

logger = get_logger(__name__)

URL_ADAPTER = TypeAdapter(HttpUrl)

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


def normalize_url(raw_url: str) -> str:
    """Normalize and validate the incoming URL string.

    Args:
        raw_url: URL provided by the client.

    Returns:
        Validated and normalized URL string.
    """
    return str(URL_ADAPTER.validate_python(raw_url)).strip()


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


def _normalize_platform(platform: str | None) -> str | None:
    """Lowercase and trim platform strings."""
    if not platform:
        return None
    return platform.strip().lower() or None


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


def analyze_and_classify_url(
    url: str,
    provided_type: ContentType | None = None,
    platform_hint: str | None = None,
) -> tuple[ContentType, str | None, dict[str, Any]]:
    """Analyze URL and determine content type, platform, and metadata.

    Uses OpenAI web search for unknown URLs, falls back to pattern matching
    if the LLM call fails or for known platforms.

    Args:
        url: Normalized URL to analyze.
        provided_type: Optional explicit content type from client.
        platform_hint: Optional platform hint from client.

    Returns:
        Tuple of (content_type, platform, extra_metadata).
        extra_metadata may contain: audio_url, media_format, extracted_title,
        duration, is_video, video_url.
    """
    extra_metadata: dict[str, Any] = {}

    # If explicit type provided, trust it and skip analysis
    if provided_type:
        platform = _normalize_platform(platform_hint)
        return provided_type, platform, extra_metadata

    # For known platforms, use fast pattern-based detection
    if not should_use_llm_analysis(url):
        content_type, platform = infer_content_type_and_platform(url, None, platform_hint)
        logger.debug(
            "Using pattern-based detection for known platform: type=%s, platform=%s",
            content_type.value,
            platform,
        )
        return content_type, platform, extra_metadata

    # Use LLM analysis for unknown URLs
    try:
        analyzer = get_content_analyzer()
        result = analyzer.analyze_url(url)

        if isinstance(result, AnalysisError):
            logger.warning(
                "LLM analysis failed, falling back to pattern detection: %s",
                result.message,
                extra={
                    "component": "content_submission",
                    "operation": "analyze_and_classify_url",
                    "context_data": {"url": url, "error": result.message},
                },
            )
            content_type, platform = infer_content_type_and_platform(url, None, platform_hint)
            return content_type, platform, extra_metadata

        # Map analysis result to ContentType
        if result.content_type == "article":
            content_type = ContentType.ARTICLE
        elif result.content_type in ("podcast", "video"):
            # Both podcast and video are processed through podcast pipeline
            content_type = ContentType.PODCAST
        else:
            content_type = ContentType.ARTICLE

        # Use detected platform or fall back to hint
        platform = result.platform or _normalize_platform(platform_hint)

        # Store extracted metadata for use by workers
        if result.media_url:
            extra_metadata["audio_url"] = result.media_url
            if result.media_format:
                extra_metadata["media_format"] = result.media_format

        if result.title:
            extra_metadata["extracted_title"] = result.title

        if result.description:
            extra_metadata["extracted_description"] = result.description

        if result.duration_seconds:
            extra_metadata["duration"] = result.duration_seconds

        if result.content_type == "video":
            extra_metadata["is_video"] = True
            extra_metadata["video_url"] = url

        logger.info(
            "LLM analysis complete: type=%s, platform=%s, has_media_url=%s",
            content_type.value,
            platform,
            result.media_url is not None,
            extra={
                "component": "content_submission",
                "operation": "analyze_and_classify_url",
                "context_data": {
                    "url": url,
                    "content_type": content_type.value,
                    "platform": platform,
                    "has_media_url": result.media_url is not None,
                    "confidence": result.confidence,
                },
            },
        )

        return content_type, platform, extra_metadata

    except Exception as e:
        logger.exception(
            "Unexpected error in LLM analysis, falling back to pattern detection: %s",
            e,
            extra={
                "component": "content_submission",
                "operation": "analyze_and_classify_url",
                "context_data": {"url": url, "error": str(e)},
            },
        )
        content_type, platform = infer_content_type_and_platform(url, None, platform_hint)
        return content_type, platform, extra_metadata


def _ensure_processing_task(db: Session, content_id: int) -> int:
    """Create a processing task if one is not already pending/processing.

    Args:
        db: Active database session.
        content_id: Content identifier to process.

    Returns:
        ProcessingTask ID.
    """
    existing_task = (
        db.query(ProcessingTask)
        .filter(ProcessingTask.content_id == content_id)
        .filter(ProcessingTask.task_type == TaskType.PROCESS_CONTENT.value)
        .filter(ProcessingTask.status.in_([TaskStatus.PENDING.value, TaskStatus.PROCESSING.value]))
        .first()
    )
    if existing_task:
        return existing_task.id

    task = ProcessingTask(
        task_type=TaskType.PROCESS_CONTENT.value,
        content_id=content_id,
        payload={"content_id": content_id},
        status=TaskStatus.PENDING.value,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task.id


def submit_user_content(
    db: Session, payload: SubmitContentRequest, current_user: User
) -> ContentSubmissionResponse:
    """Persist and enqueue a user-submitted article or podcast.

    Uses LLM-powered content analysis for unknown URLs to determine content type
    and extract media URLs. Falls back to pattern-based detection for known
    platforms or on analysis failure.

    Args:
        db: Active database session.
        payload: Submission request payload.
        current_user: Authenticated user submitting the URL.

    Returns:
        Submission response describing the created or existing content.
    """
    normalized_url = normalize_url(str(payload.url))
    explicit_type = ContentType(payload.content_type) if payload.content_type else None

    # Use LLM-powered analysis for unknown URLs, pattern matching for known platforms
    content_type, platform, extra_metadata = analyze_and_classify_url(
        normalized_url, explicit_type, payload.platform
    )

    existing = (
        db.query(Content)
        .filter(Content.url == normalized_url)
        .filter(Content.content_type == content_type.value)
        .first()
    )
    if existing:
        status_created = ensure_inbox_status(
            db, current_user.id, existing.id, content_type=content_type.value
        )
        if status_created:
            db.commit()
        task_id = _ensure_processing_task(db, existing.id)
        return ContentSubmissionResponse(
            content_id=existing.id,
            content_type=content_type,
            status=ContentStatus(existing.status),
            platform=existing.platform,
            already_exists=True,
            message="Content already submitted; using existing record",
            task_id=task_id,
            source=existing.source or SELF_SUBMISSION_SOURCE,
        )

    # Build metadata with LLM-extracted info
    metadata = {
        "source": SELF_SUBMISSION_SOURCE,
        "platform": platform,
        "submitted_by_user_id": current_user.id,
        "submitted_via": "share_sheet",
        **extra_metadata,  # Include audio_url, extracted_title, etc.
    }

    # Use extracted title if no client title provided
    title = payload.title
    if not title and extra_metadata.get("extracted_title"):
        title = extra_metadata["extracted_title"]

    new_content = Content(
        url=normalized_url,
        content_type=content_type.value,
        title=title,
        source=SELF_SUBMISSION_SOURCE,
        platform=platform,
        is_aggregate=False,
        status=ContentStatus.NEW.value,
        classification=ContentClassification.TO_READ.value,
        content_metadata=metadata,
    )

    db.add(new_content)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        logger.warning("Self-submission hit duplicate constraint for %s: %s", normalized_url, exc)
        existing = (
            db.query(Content)
            .filter(Content.url == normalized_url)
            .filter(Content.content_type == content_type.value)
            .first()
        )
        if not existing:
            raise
        task_id = _ensure_processing_task(db, existing.id)
        return ContentSubmissionResponse(
            content_id=existing.id,
            content_type=content_type,
            status=ContentStatus(existing.status),
            platform=existing.platform,
            already_exists=True,
            message="Content already submitted; using existing record",
            task_id=task_id,
            source=existing.source or SELF_SUBMISSION_SOURCE,
        )

    db.refresh(new_content)
    status_created = ensure_inbox_status(
        db, current_user.id, new_content.id, content_type=content_type.value
    )
    if status_created:
        db.commit()
    task_id = _ensure_processing_task(db, new_content.id)

    return ContentSubmissionResponse(
        content_id=new_content.id,
        content_type=content_type,
        status=ContentStatus(new_content.status),
        platform=platform,
        already_exists=False,
        message="Content queued for processing",
        task_id=task_id,
        source=new_content.source or SELF_SUBMISSION_SOURCE,
    )
