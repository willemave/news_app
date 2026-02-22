"""Tests for X API URL normalization helpers."""

from app.services.x_api import _normalize_external_url


def test_normalize_external_url_keeps_non_social_domains() -> None:
    """Domains that merely end with similar letters must not be filtered."""
    assert _normalize_external_url("https://index.com/article") == "https://index.com/article"
    assert (
        _normalize_external_url("https://mytwitter.com/post/1")
        == "https://mytwitter.com/post/1"
    )


def test_normalize_external_url_filters_x_twitter_domains() -> None:
    """X/Twitter domains and subdomains are excluded from fanout URLs."""
    assert _normalize_external_url("https://x.com/user/status/1") is None
    assert _normalize_external_url("https://mobile.twitter.com/user/status/1") is None
    assert _normalize_external_url("https://news.x.com/path") is None
