"""Helpers for subscribing to detected RSS/Atom feeds."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse, urlunparse

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.schema import UserScraperConfig
from app.services.scraper_configs import (
    ALLOWED_SCRAPER_TYPES,
    CreateUserScraperConfig,
    create_user_scraper_config,
)

logger = get_logger(__name__)


def _normalize_feed_url_for_lookup(feed_url: str) -> str:
    trimmed = feed_url.strip()
    try:
        parsed = urlparse(trimmed)
    except Exception:
        return trimmed.rstrip("/")

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or parsed.path
    normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path)
    return urlunparse(normalized)


def is_feed_already_subscribed(
    db: Session,
    user_id: int,
    feed_type: str,
    feed_url: str,
) -> bool:
    """Check whether the user already has an active config for the feed."""
    if not feed_url.strip():
        return False

    normalized_target = _normalize_feed_url_for_lookup(feed_url)

    configs = (
        db.query(UserScraperConfig.feed_url)
        .filter(UserScraperConfig.user_id == user_id)
        .filter(UserScraperConfig.scraper_type == feed_type)
        .filter(UserScraperConfig.is_active.is_(True))
        .all()
    )
    for (existing_url,) in configs:
        if not existing_url:
            continue
        if _normalize_feed_url_for_lookup(existing_url) == normalized_target:
            return True
    return False


def can_subscribe_to_feed(
    db: Session,
    user_id: int | None,
    detected_feed: dict[str, Any] | None,
) -> bool:
    """Return True if the detected feed can be subscribed to for this user."""
    if user_id is None:
        return False
    if not isinstance(detected_feed, dict):
        return False

    feed_url = detected_feed.get("url")
    feed_type = detected_feed.get("type")
    if not isinstance(feed_url, str) or not feed_url.strip():
        return False
    if not isinstance(feed_type, str) or not feed_type.strip():
        return False
    if feed_type not in ALLOWED_SCRAPER_TYPES:
        return False

    return not is_feed_already_subscribed(db, user_id, feed_type, feed_url)


def subscribe_to_detected_feed(
    db: Session,
    user_id: int | None,
    detected_feed: dict[str, Any] | None,
    *,
    display_name: str | None = None,
) -> tuple[bool, str]:
    """Create a scraper config for a detected feed.

    Args:
        db: Active database session.
        user_id: User identifier (required).
        detected_feed: Dict containing feed details (url/type/title/format).
        display_name: Optional display name to store with the feed config.

    Returns:
        Tuple of (created, status). Status is a short string describing the outcome.
    """
    if user_id is None:
        return False, "missing_user"
    if not isinstance(detected_feed, dict):
        return False, "missing_feed"

    feed_url = detected_feed.get("url")
    feed_type = detected_feed.get("type")
    if not isinstance(feed_url, str) or not feed_url.strip():
        return False, "missing_feed_url"
    if not isinstance(feed_type, str) or not feed_type.strip():
        return False, "missing_feed_type"
    if feed_type not in ALLOWED_SCRAPER_TYPES:
        return False, "unsupported_feed_type"

    payload = CreateUserScraperConfig(
        scraper_type=feed_type,
        display_name=display_name,
        config={"feed_url": feed_url.strip()},
        is_active=True,
    )

    try:
        create_user_scraper_config(db, user_id, payload)
    except ValueError as exc:
        logger.info(
            "Feed subscription skipped for user %s: %s",
            user_id,
            exc,
            extra={
                "component": "feed_subscription",
                "operation": "subscribe",
                "context_data": {"feed_url": feed_url, "feed_type": feed_type},
            },
        )
        return False, "already_exists"

    return True, "created"
