from __future__ import annotations

from app.services.podcast_search import PodcastEpisodeSearchHit, search_podcast_episodes


def _build_hit(
    *,
    title: str,
    url: str,
    provider: str,
    score: float,
    podcast_title: str | None = None,
) -> PodcastEpisodeSearchHit:
    return PodcastEpisodeSearchHit(
        title=title,
        episode_url=url,
        podcast_title=podcast_title,
        source=None,
        snippet=None,
        feed_url=None,
        published_at=None,
        provider=provider,
        score=score,
    )


def test_search_podcast_episodes_merges_and_dedupes(monkeypatch):
    from app.services import podcast_search

    podcast_search._SEARCH_CACHE.clear()
    podcast_search._PROVIDER_STATES.clear()

    monkeypatch.setattr(
        podcast_search,
        "_search_listen_notes",
        lambda _query, _limit: [
            _build_hit(
                title="OpenAI Dev Day Podcast Episode",
                url="https://example.fm/episodes/dev-day?utm_source=test",
                provider="listen_notes",
                score=0.95,
                podcast_title="AI Weekly",
            )
        ],
    )
    monkeypatch.setattr(
        podcast_search,
        "_search_spotify",
        lambda _query, _limit: [
            _build_hit(
                title="OpenAI release recap",
                url="https://open.spotify.com/episode/abc123?si=tracking",
                provider="spotify",
                score=0.9,
                podcast_title="AI Daily",
            )
        ],
    )
    monkeypatch.setattr(
        podcast_search,
        "_search_apple_itunes",
        lambda _query, _limit: [],
    )
    monkeypatch.setattr(
        podcast_search,
        "_search_podcast_index",
        lambda _query, _limit: [],
    )
    monkeypatch.setattr(
        podcast_search,
        "_search_exa",
        lambda _query, _limit: [
            _build_hit(
                title="Duplicate episode result from Exa",
                url="https://example.fm/episodes/dev-day",
                provider="exa",
                score=0.6,
                podcast_title="AI Weekly",
            )
        ],
    )

    hits = search_podcast_episodes("openai dev day", limit=10)

    assert len(hits) == 2
    assert hits[0].provider == "listen_notes"
    assert hits[0].episode_url.startswith("https://example.fm/episodes/dev-day")
    assert hits[1].provider == "spotify"


def test_search_podcast_episodes_short_query_returns_empty(monkeypatch):
    from app.services import podcast_search

    podcast_search._SEARCH_CACHE.clear()
    podcast_search._PROVIDER_STATES.clear()

    called = False

    def _stub_provider(_query: str, _limit: int):
        nonlocal called
        called = True
        return []

    monkeypatch.setattr(podcast_search, "_search_listen_notes", _stub_provider)
    monkeypatch.setattr(podcast_search, "_search_spotify", _stub_provider)
    monkeypatch.setattr(podcast_search, "_search_apple_itunes", _stub_provider)
    monkeypatch.setattr(podcast_search, "_search_podcast_index", _stub_provider)
    monkeypatch.setattr(podcast_search, "_search_exa", _stub_provider)

    hits = search_podcast_episodes("x", limit=5)

    assert hits == []
    assert called is False
