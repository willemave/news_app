from __future__ import annotations

from app.services.onboarding import _DiscoverSuggestion, _normalize_suggestions


def test_normalize_suggestions_uses_candidate_feed_url_when_feed_url_missing() -> None:
    items = [
        _DiscoverSuggestion(
            title="Marine Science Weekly",
            site_url="https://example.org/newsletter",
            candidate_feed_url="https://example.org/rss.xml",
            is_likely_feed=True,
            feed_confidence=0.81,
        )
    ]

    normalized = _normalize_suggestions(items, "substack")

    assert len(normalized) == 1
    assert normalized[0].feed_url == "https://example.org/rss.xml"


def test_normalize_suggestions_uses_likely_feed_site_when_feed_like() -> None:
    items = [
        _DiscoverSuggestion(
            title="Ocean Dispatch",
            site_url="https://example.org/podcast-feed.xml",
            is_likely_feed=True,
            feed_confidence=0.74,
        )
    ]

    normalized = _normalize_suggestions(items, "podcast_rss")

    assert len(normalized) == 1
    assert normalized[0].feed_url == "https://example.org/podcast-feed.xml"
