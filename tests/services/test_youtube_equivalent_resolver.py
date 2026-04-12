from __future__ import annotations

from types import SimpleNamespace

from app.services.content_analyzer import AnalysisError
from app.services.exa_client import ExaSearchResult
from app.services.podcast_search import PodcastEpisodeSearchHit
from app.services.youtube_equivalent_resolver import resolve_youtube_equivalent


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return self._payload


def _analysis_result(
    *,
    content_type: str,
    platform: str,
    media_url: str | None,
    title: str | None,
):
    return SimpleNamespace(
        analysis=SimpleNamespace(
            content_type=content_type,
            platform=platform,
            media_url=media_url,
            media_format="mp3" if media_url else None,
            title=title,
        )
    )


def test_resolve_youtube_equivalent_uses_metadata_and_validates_non_youtube_match(monkeypatch):
    from app.services import youtube_equivalent_resolver as resolver

    monkeypatch.setattr(
        resolver.httpx,
        "get",
        lambda *_args, **_kwargs: _Response(
            {
                "title": "The Future of Software Engineering with AI | Spiros Xanthos, Resolve AI",
                "author_name": "Lightspeed Venture Partners",
                "author_url": "https://www.youtube.com/@lightspeedvp",
                "thumbnail_url": "https://i.ytimg.com/vi/6rZ-ruRKQ4Q/hqdefault.jpg",
            }
        ),
    )

    recorded_queries: list[str] = []

    def _fake_podcast_search(query: str, limit: int):
        recorded_queries.append(query)
        return [
            PodcastEpisodeSearchHit(
                title="Unrelated Panel Episode",
                episode_url="https://podcasts.apple.com/us/podcast/unrelated-panel/id1?i=2",
                podcast_title="Other Show",
                source=None,
                snippet=None,
                feed_url=None,
                published_at=None,
                provider="apple_itunes",
                score=0.82,
            )
        ]

    monkeypatch.setattr(resolver, "search_podcast_episodes", _fake_podcast_search)
    monkeypatch.setattr(
        resolver,
        "exa_search",
        lambda *_args, **_kwargs: [
            ExaSearchResult(
                title=(
                    "The Future of Software! When AI Becomes Your Reliability Team | Spiros Xanthos"
                ),
                url=(
                    "https://podcasts.apple.com/us/podcast/"
                    "the-future-of-software-when-ai-becomes-your/"
                    "id1731487628?i=1000733551104"
                ),
                snippet="A conversation with Spiros Xanthos about Resolve AI.",
            )
        ],
    )

    class _Gateway:
        def analyze_url(self, url: str):
            if "unrelated-panel" in url:
                return _analysis_result(
                    content_type="podcast",
                    platform="apple_podcasts",
                    media_url="https://example.com/unrelated.mp3",
                    title="Unrelated Panel Episode",
                )
            return _analysis_result(
                content_type="podcast",
                platform="apple_podcasts",
                media_url="https://anchor.fm/s/example.mp3",
                title=(
                    "The Future of Software! When AI Becomes Your Reliability Team | Spiros Xanthos"
                ),
            )

    monkeypatch.setattr(resolver, "get_llm_gateway", lambda: _Gateway())

    result = resolve_youtube_equivalent("https://www.youtube.com/watch?v=6rZ-ruRKQ4Q")

    assert recorded_queries == [
        (
            "The Future of Software Engineering with AI | Spiros Xanthos, Resolve AI "
            "Lightspeed Venture Partners"
        )
    ]
    assert result.resolved_url == (
        "https://podcasts.apple.com/us/podcast/the-future-of-software-when-ai-becomes-your/"
        "id1731487628?i=1000733551104"
    )
    assert result.platform == "apple_podcasts"
    assert result.media_url == "https://anchor.fm/s/example.mp3"
    assert result.metadata is not None
    assert result.metadata.thumbnail_url == "https://i.ytimg.com/vi/6rZ-ruRKQ4Q/hqdefault.jpg"


def test_resolve_youtube_equivalent_returns_metadata_when_candidates_do_not_validate(monkeypatch):
    from app.services import youtube_equivalent_resolver as resolver

    monkeypatch.setattr(
        resolver.httpx,
        "get",
        lambda *_args, **_kwargs: _Response(
            {
                "title": "The future of intelligence | Demis Hassabis",
                "author_name": "Google DeepMind",
                "thumbnail_url": "https://i.ytimg.com/vi/PqVbypvxDto/hqdefault.jpg",
            }
        ),
    )
    monkeypatch.setattr(
        resolver,
        "search_podcast_episodes",
        lambda *_args, **_kwargs: [
            PodcastEpisodeSearchHit(
                title="The Future of Intelligence with Demis Hassabis",
                episode_url="https://example.com/transcript-wrapper",
                podcast_title="Transcript Feed",
                source=None,
                snippet="Transcript wrapper that embeds the YouTube player.",
                feed_url=None,
                published_at=None,
                provider="exa",
                score=0.6,
            )
        ],
    )
    monkeypatch.setattr(resolver, "exa_search", lambda *_args, **_kwargs: [])

    class _Gateway:
        def analyze_url(self, _url: str):
            return AnalysisError(message="not processable", recoverable=True)

    monkeypatch.setattr(resolver, "get_llm_gateway", lambda: _Gateway())

    result = resolve_youtube_equivalent("https://www.youtube.com/watch?v=PqVbypvxDto")

    assert result.resolved_url is None
    assert result.reason == "no_validated_match"
    assert result.metadata is not None
    assert result.metadata.title == "The future of intelligence | Demis Hassabis"
