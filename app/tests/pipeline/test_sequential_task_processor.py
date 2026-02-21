"""Tests for analyze_url and dig_deeper handlers."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock

from app.constants import SELF_SUBMISSION_SOURCE
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.pipeline.handlers.analyze_url import AnalyzeUrlHandler
from app.pipeline.handlers.dig_deeper import DigDeeperHandler
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope
from app.services.apple_podcasts import ApplePodcastResolution
from app.services.content_analyzer import (
    ContentAnalysisOutput,
    ContentAnalysisResult,
    InstructionLink,
    InstructionResult,
)
from app.services.queue import TaskType
from app.services.x_api import XTweet, XTweetFetchResult


def _build_analysis_output(url: str) -> ContentAnalysisOutput:
    """Create a deterministic analyzer output with instruction links."""
    return ContentAnalysisOutput(
        analysis=ContentAnalysisResult(content_type="article", original_url=url),
        instruction=InstructionResult(
            text="Related links",
            links=[InstructionLink(url="https://example.com/related")],
        ),
    )


def _create_content(db_session, user_id: int, url: str) -> Content:
    """Create a minimal content row for analyze_url tests."""
    content = Content(
        url=url,
        content_type=ContentType.UNKNOWN.value,
        status=ContentStatus.NEW.value,
        source=SELF_SUBMISSION_SOURCE,
        content_metadata={
            "submitted_by_user_id": user_id,
            "submitted_via": "share_sheet",
        },
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def _build_context(db_session) -> TaskContext:
    @contextmanager
    def _db_context():
        yield db_session

    return TaskContext(
        queue_service=Mock(),
        settings=Mock(),
        llm_service=Mock(),
        worker_id="test-worker",
        db_factory=_db_context,
    )


def _patch_analyze_dependencies(monkeypatch, analyzer_output: ContentAnalysisOutput):
    from app.pipeline.handlers import analyze_url as analyze_module

    stub_analyzer = Mock()
    stub_analyzer.analyze_url.return_value = analyzer_output

    monkeypatch.setattr(analyze_module, "get_content_analyzer", lambda: stub_analyzer)
    return stub_analyzer


def _build_tweet_fetch_result(external_urls: list[str]) -> XTweetFetchResult:
    tweet = XTweet(
        id="123",
        text="Main tweet",
        author_username="alice",
        author_name="Alice",
        created_at="2026-02-21T10:00:00Z",
        external_urls=external_urls,
    )
    return XTweetFetchResult(success=True, tweet=tweet)


def test_analyze_url_skips_instruction_links_when_crawl_disabled(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://example.com/article")
    analysis_output = _build_analysis_output(content.url)

    stub_analyzer = _patch_analyze_dependencies(monkeypatch, analysis_output)
    create_mock = Mock(return_value=[])
    from app.pipeline.handlers import analyze_url as analyze_module

    monkeypatch.setattr(analyze_module, "create_contents_from_instruction_links", create_mock)

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=1,
        task_type=TaskType.ANALYZE_URL,
        payload={
            "content_id": content.id,
            "instruction": "Find related links",
            "crawl_links": False,
        },
    )

    assert handler.handle(task, context).success is True
    stub_analyzer.analyze_url.assert_called_once()
    create_mock.assert_not_called()


def test_analyze_url_creates_instruction_links_when_crawl_enabled(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://example.com/article")
    analysis_output = _build_analysis_output(content.url)

    stub_analyzer = _patch_analyze_dependencies(monkeypatch, analysis_output)
    create_mock = Mock(return_value=[])
    from app.pipeline.handlers import analyze_url as analyze_module

    monkeypatch.setattr(analyze_module, "create_contents_from_instruction_links", create_mock)

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=2,
        task_type=TaskType.ANALYZE_URL,
        payload={
            "content_id": content.id,
            "crawl_links": True,
        },
    )

    assert handler.handle(task, context).success is True
    stub_analyzer.analyze_url.assert_called_once_with(
        content.url,
        instruction="Extract relevant links from the submitted page.",
    )
    create_mock.assert_called_once()


def test_analyze_url_apple_podcasts_resolves_audio_url(
    db_session,
    test_user,
    monkeypatch,
):
    url = "https://podcasts.apple.com/us/podcast/episode-title/id1592743188?i=1000745113618"
    content = _create_content(db_session, test_user.id, url)

    from app.pipeline.handlers import analyze_url as analyze_module

    monkeypatch.setattr(
        analyze_module,
        "resolve_apple_podcast_episode",
        lambda _: ApplePodcastResolution(
            feed_url="https://example.com/feed.xml",
            episode_title="Example Episode",
            audio_url="https://example.com/audio.mp3",
        ),
    )
    monkeypatch.setattr(analyze_module, "get_content_analyzer", Mock())

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=3,
        task_type=TaskType.ANALYZE_URL,
        payload={"content_id": content.id},
    )

    assert handler.handle(task, context).success is True

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.content_metadata.get("audio_url") == "https://example.com/audio.mp3"
    assert updated.content_metadata.get("feed_url") == "https://example.com/feed.xml"
    assert updated.content_metadata.get("episode_title") == "Example Episode"
    assert updated.title == "Example Episode"


def test_analyze_url_youtube_single_video_sets_audio_metadata(
    db_session,
    test_user,
    monkeypatch,
):
    url = "https://www.youtube.com/watch?v=abc123xyz"
    content = _create_content(db_session, test_user.id, url)

    from app.pipeline.handlers import analyze_url as analyze_module

    analyzer_mock = Mock()
    monkeypatch.setattr(analyze_module, "get_content_analyzer", lambda: analyzer_mock)

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=8,
        task_type=TaskType.ANALYZE_URL,
        payload={"content_id": content.id},
    )

    assert handler.handle(task, context).success is True
    analyzer_mock.analyze_url.assert_not_called()

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.content_type == ContentType.PODCAST.value
    assert updated.platform == "youtube"
    assert updated.content_metadata.get("audio_url") == url
    assert updated.content_metadata.get("video_url") == url
    assert updated.content_metadata.get("youtube_video") is True


def test_analyze_url_llm_youtube_podcast_sets_fallback_audio_metadata(
    db_session,
    test_user,
    monkeypatch,
):
    url = "https://www.youtube.com/watch?v=abc123xyz"
    content = _create_content(db_session, test_user.id, url)

    analysis_output = ContentAnalysisOutput(
        analysis=ContentAnalysisResult(
            content_type="podcast",
            original_url=url,
            platform="youtube",
            media_url=None,
        )
    )

    stub_analyzer = _patch_analyze_dependencies(monkeypatch, analysis_output)

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=10,
        task_type=TaskType.ANALYZE_URL,
        payload={
            "content_id": content.id,
            "instruction": "Classify and extract media metadata.",
        },
    )

    assert handler.handle(task, context).success is True
    stub_analyzer.analyze_url.assert_called_once()

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.content_type == ContentType.PODCAST.value
    assert updated.platform == "youtube"
    assert updated.content_metadata.get("audio_url") == url
    assert updated.content_metadata.get("video_url") == url
    assert updated.content_metadata.get("youtube_video") is True


def test_analyze_url_spotify_share_stays_article(
    db_session,
    test_user,
    monkeypatch,
):
    url = "https://open.spotify.com/episode/abc123"
    content = _create_content(db_session, test_user.id, url)

    from app.pipeline.handlers import analyze_url as analyze_module

    analyzer_mock = Mock()
    monkeypatch.setattr(analyze_module, "get_content_analyzer", lambda: analyzer_mock)

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=9,
        task_type=TaskType.ANALYZE_URL,
        payload={"content_id": content.id},
    )

    assert handler.handle(task, context).success is True
    analyzer_mock.analyze_url.assert_not_called()

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.content_type == ContentType.ARTICLE.value
    assert updated.platform == "spotify"
    assert updated.content_metadata.get("audio_url") is None


def test_dig_deeper_task_runs_chat_flow(db_session, test_user, monkeypatch):
    content = _create_content(db_session, test_user.id, "https://example.com/article")

    from app.pipeline.handlers import dig_deeper as dig_module

    create_mock = Mock(return_value=(123, 456, "prompt"))
    run_mock = Mock()
    monkeypatch.setattr(dig_module, "create_dig_deeper_message", create_mock)
    monkeypatch.setattr(dig_module, "run_dig_deeper_message", run_mock)

    handler = DigDeeperHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=4,
        task_type=TaskType.DIG_DEEPER,
        content_id=content.id,
        payload={"user_id": test_user.id},
    )

    assert handler.handle(task, context).success is True
    create_mock.assert_called_once_with(db_session, content, test_user.id)
    run_mock.assert_called_once_with(123, 456, "prompt", task_id=4)


def test_analyze_url_subscribe_to_feed_short_circuits_processing(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://example.com/article")

    from app.pipeline.handlers import analyze_url as analyze_module

    class DummyHttpService:
        def fetch_content(self, url):  # noqa: ANN001
            html = (
                '<link rel="alternate" type="application/rss+xml" '
                'href="https://example.com/feed" title="Example Feed" />'
            )
            return f"<html><head>{html}</head><body></body></html>", {}

    monkeypatch.setattr(analyze_module, "get_http_service", lambda: DummyHttpService())
    monkeypatch.setattr(
        analyze_module,
        "detect_feeds_from_html",
        lambda html, page_url, page_title=None, source=None, content_type=None: {
            "detected_feed": {
                "url": "https://example.com/feed",
                "type": "atom",
                "title": "Example Feed",
                "format": "rss",
            }
        },
    )
    subscribe_mock = Mock(return_value=(True, "created"))
    monkeypatch.setattr(analyze_module, "subscribe_to_detected_feed", subscribe_mock)
    monkeypatch.setattr(analyze_module, "get_content_analyzer", Mock())

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=5,
        task_type=TaskType.ANALYZE_URL,
        payload={"content_id": content.id, "subscribe_to_feed": True},
    )

    assert handler.handle(task, context).success is True
    context.queue_service.enqueue.assert_not_called()

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.status == ContentStatus.SKIPPED.value
    assert updated.content_metadata.get("subscribe_to_feed") is True
    assert updated.content_metadata.get("detected_feed", {}).get("url") == (
        "https://example.com/feed"
    )
    assert updated.content_metadata.get("feed_subscription", {}).get("status") == "created"
    subscribe_mock.assert_called_once()


def test_analyze_url_tweet_fanout_creates_additional_content(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://x.com/user/status/123")

    from app.pipeline.handlers import analyze_url as analyze_module

    monkeypatch.setattr(
        analyze_module,
        "fetch_tweet_by_id",
        lambda tweet_id, access_token=None: _build_tweet_fetch_result(
            ["https://example.com/a", "https://example.com/b"]
        ),
    )
    monkeypatch.setattr(analyze_module, "get_x_user_access_token", lambda db, user_id: None)

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=6,
        task_type=TaskType.ANALYZE_URL,
        payload={"content_id": content.id},
    )

    assert handler.handle(task, context).success is True

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.url == "https://example.com/a"
    assert updated.source_url == "https://x.com/i/status/123"
    assert updated.content_metadata.get("discussion_url") == "https://x.com/i/status/123"

    fanout = db_session.query(Content).filter(Content.url == "https://example.com/b").first()
    assert fanout is not None
    assert fanout.source_url == "https://x.com/i/status/123"


def test_analyze_url_tweet_only_uses_thread_text(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://twitter.com/user/status/123")

    from app.pipeline.handlers import analyze_url as analyze_module

    monkeypatch.setattr(
        analyze_module,
        "fetch_tweet_by_id",
        lambda tweet_id, access_token=None: _build_tweet_fetch_result([]),
    )
    monkeypatch.setattr(analyze_module, "get_x_user_access_token", lambda db, user_id: None)

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=7,
        task_type=TaskType.ANALYZE_URL,
        payload={"content_id": content.id},
    )

    assert handler.handle(task, context).success is True

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.url == "https://x.com/i/status/123"
    assert updated.content_metadata.get("tweet_only") is True
    assert updated.content_metadata.get("tweet_thread_text") == "Main tweet"


def test_analyze_url_tweet_lookup_missing_app_auth_degrades_gracefully(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://x.com/user/status/123")

    from app.pipeline.handlers import analyze_url as analyze_module

    monkeypatch.setattr(
        analyze_module,
        "fetch_tweet_by_id",
        lambda tweet_id, access_token=None: XTweetFetchResult(
            success=False,
            error="X_APP_BEARER_TOKEN is required for app-authenticated X requests",
        ),
    )
    monkeypatch.setattr(analyze_module, "get_x_user_access_token", lambda db, user_id: None)
    analyzer_mock = Mock()
    monkeypatch.setattr(analyze_module, "get_content_analyzer", lambda: analyzer_mock)

    handler = AnalyzeUrlHandler()
    context = _build_context(db_session)

    task = TaskEnvelope(
        id=11,
        task_type=TaskType.ANALYZE_URL,
        payload={"content_id": content.id},
    )

    assert handler.handle(task, context).success is True

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.status != ContentStatus.FAILED.value
    assert updated.content_metadata.get("tweet_enrichment", {}).get("status") == "skipped"
    assert updated.content_metadata.get("tweet_enrichment", {}).get("reason") == (
        "x_app_auth_unavailable"
    )
