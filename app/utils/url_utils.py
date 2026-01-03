"""URL normalization helpers."""

from __future__ import annotations

from urllib.parse import urlparse


def is_http_url(value: str | None) -> bool:
    """Return True when value is a valid http(s) URL."""
    if not value or not isinstance(value, str):
        return False
    try:
        parsed = urlparse(value.strip())
    except Exception:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def normalize_http_url(value: str | None) -> str | None:
    """Normalize a URL to https and strip whitespace, returning None when invalid."""
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        parsed = urlparse(cleaned)
    except Exception:
        return None
    scheme = parsed.scheme or "https"
    if scheme not in {"http", "https"}:
        return None
    normalized = parsed._replace(scheme=scheme)
    url = normalized.geturl()
    if url.startswith("http://"):
        url = "https://" + url[len("http://") :]
    return url
