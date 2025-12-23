"""Helpers for user-submitted one-off content."""

from __future__ import annotations

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


def _ensure_analyze_url_task(db: Session, content_id: int) -> int:
    """Create an ANALYZE_URL task if one is not already pending/processing.

    Args:
        db: Active database session.
        content_id: Content identifier to analyze.

    Returns:
        ProcessingTask ID.
    """
    # Check for existing ANALYZE_URL or PROCESS_CONTENT task
    existing_task = (
        db.query(ProcessingTask)
        .filter(ProcessingTask.content_id == content_id)
        .filter(
            ProcessingTask.task_type.in_(
                [TaskType.ANALYZE_URL.value, TaskType.PROCESS_CONTENT.value]
            )
        )
        .filter(ProcessingTask.status.in_([TaskStatus.PENDING.value, TaskStatus.PROCESSING.value]))
        .first()
    )
    if existing_task:
        return existing_task.id

    task = ProcessingTask(
        task_type=TaskType.ANALYZE_URL.value,
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
    """Persist and enqueue a user-submitted URL for async analysis.

    Creates content with UNKNOWN type and enqueues ANALYZE_URL task.
    The async task will determine content type (via pattern matching or LLM)
    and then enqueue PROCESS_CONTENT.

    Args:
        db: Active database session.
        payload: Submission request payload.
        current_user: Authenticated user submitting the URL.

    Returns:
        Submission response describing the created or existing content.
    """
    normalized_url = normalize_url(str(payload.url))

    # Check if content already exists (by URL only, regardless of type)
    existing = db.query(Content).filter(Content.url == normalized_url).first()
    if existing:
        status_created = ensure_inbox_status(
            db, current_user.id, existing.id, content_type=existing.content_type
        )
        if status_created:
            db.commit()
        task_id = _ensure_analyze_url_task(db, existing.id)
        return ContentSubmissionResponse(
            content_id=existing.id,
            content_type=ContentType(existing.content_type),
            status=ContentStatus(existing.status),
            platform=existing.platform,
            already_exists=True,
            message="Content already submitted; using existing record",
            task_id=task_id,
            source=existing.source or SELF_SUBMISSION_SOURCE,
        )

    # Build initial metadata
    metadata = {
        "source": SELF_SUBMISSION_SOURCE,
        "submitted_by_user_id": current_user.id,
        "submitted_via": "share_sheet",
    }

    # Create content with UNKNOWN type - will be updated by ANALYZE_URL task
    new_content = Content(
        url=normalized_url,
        content_type=ContentType.UNKNOWN.value,
        title=payload.title,
        source=SELF_SUBMISSION_SOURCE,
        platform=None,
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
        existing = db.query(Content).filter(Content.url == normalized_url).first()
        if not existing:
            raise
        task_id = _ensure_analyze_url_task(db, existing.id)
        return ContentSubmissionResponse(
            content_id=existing.id,
            content_type=ContentType(existing.content_type),
            status=ContentStatus(existing.status),
            platform=existing.platform,
            already_exists=True,
            message="Content already submitted; using existing record",
            task_id=task_id,
            source=existing.source or SELF_SUBMISSION_SOURCE,
        )

    db.refresh(new_content)
    status_created = ensure_inbox_status(
        db, current_user.id, new_content.id, content_type=new_content.content_type
    )
    if status_created:
        db.commit()
    task_id = _ensure_analyze_url_task(db, new_content.id)

    return ContentSubmissionResponse(
        content_id=new_content.id,
        content_type=ContentType.UNKNOWN,
        status=ContentStatus(new_content.status),
        platform=None,
        already_exists=False,
        message="Content queued for analysis",
        task_id=task_id,
        source=new_content.source or SELF_SUBMISSION_SOURCE,
    )
