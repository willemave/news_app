"""Helpers for subscribing to detected RSS/Atom feeds."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.scraper_configs import (
    ALLOWED_SCRAPER_TYPES,
    CreateUserScraperConfig,
    create_user_scraper_config,
)

logger = get_logger(__name__)


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
