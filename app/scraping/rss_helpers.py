"""Helpers for shared RSS/Atom feed handling."""

from __future__ import annotations

from urllib.parse import urlparse


def resolve_feed_source(
    display_name: str | None,
    feed_title: str | None,
    feed_url: str | None,
) -> str | None:
    """Resolve feed source name using display name, feed title, then domain."""
    if display_name and display_name.strip():
        return display_name.strip()
    if feed_title and feed_title.strip():
        return feed_title.strip()
    if not feed_url:
        return None
    try:
        parsed = urlparse(feed_url)
    except Exception:
        return None
    domain = parsed.netloc or ""
    if domain.startswith("www."):
        domain = domain[4:]
    return domain or None
