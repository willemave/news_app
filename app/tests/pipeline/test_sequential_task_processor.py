"""Tests for analyze_url task handling in the sequential task processor."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock

from app.constants import SELF_SUBMISSION_SOURCE
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.pipeline import sequential_task_processor as stp
from app.services.content_analyzer import (
    ContentAnalysisOutput,
    ContentAnalysisResult,
    InstructionLink,
    InstructionResult,
)
from app.services.twitter_share import (
    TweetFetchResult,
    TweetInfo,
    TwitterCredentials,
    TwitterCredentialsResult,
)


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


def _patch_processor_dependencies(db_session, monkeypatch, analyzer_output: ContentAnalysisOutput):
    stub_analyzer = Mock()
    stub_analyzer.analyze_url.return_value = analyzer_output

    @contextmanager
    def _db_context():
        yield db_session

    monkeypatch.setattr(stp, "get_db", _db_context)
    monkeypatch.setattr(stp, "get_content_analyzer", lambda: stub_analyzer)
    monkeypatch.setattr(stp, "get_llm_service", lambda: None)

    return stub_analyzer


def _build_tweet_fetch_result(external_urls: list[str]) -> TweetFetchResult:
    tweet = TweetInfo(
        id="123",
        text="Main tweet",
        author_username="alice",
        author_name="Alice",
        created_at="Wed Oct 05 20:17:27 +0000 2022",
    )
    thread = [
        tweet,
        TweetInfo(
            id="124",
            text="Thread follow-up",
            author_username="alice",
            author_name="Alice",
            created_at="Wed Oct 05 20:18:27 +0000 2022",
            conversation_id="conv1",
        ),
    ]
    return TweetFetchResult(
        success=True,
        tweet=tweet,
        thread=thread,
        external_urls=external_urls,
    )


def test_analyze_url_skips_instruction_links_when_crawl_disabled(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://example.com/article")
    analysis_output = _build_analysis_output(content.url)

    stub_analyzer = _patch_processor_dependencies(db_session, monkeypatch, analysis_output)
    create_mock = Mock(return_value=[])
    monkeypatch.setattr(stp, "create_contents_from_instruction_links", create_mock)

    processor = stp.SequentialTaskProcessor()
    processor.queue_service.enqueue = Mock()

    task_data = {
        "task_type": stp.TaskType.ANALYZE_URL.value,
        "payload": {
            "content_id": content.id,
            "instruction": "Find related links",
            "crawl_links": False,
        },
    }

    assert processor._process_analyze_url_task(task_data) is True
    stub_analyzer.analyze_url.assert_called_once()
    create_mock.assert_not_called()


def test_analyze_url_creates_instruction_links_when_crawl_enabled(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://example.com/article")
    analysis_output = _build_analysis_output(content.url)

    stub_analyzer = _patch_processor_dependencies(db_session, monkeypatch, analysis_output)
    create_mock = Mock(return_value=[])
    monkeypatch.setattr(stp, "create_contents_from_instruction_links", create_mock)

    processor = stp.SequentialTaskProcessor()
    processor.queue_service.enqueue = Mock()

    task_data = {
        "task_type": stp.TaskType.ANALYZE_URL.value,
        "payload": {
            "content_id": content.id,
            "crawl_links": True,
        },
    }

    assert processor._process_analyze_url_task(task_data) is True
    stub_analyzer.analyze_url.assert_called_once_with(
        content.url,
        instruction="Extract relevant links from the submitted page.",
    )
    create_mock.assert_called_once()


def test_analyze_url_subscribe_to_feed_short_circuits_processing(
    db_session,
    test_user,
    monkeypatch,
):
    content = _create_content(db_session, test_user.id, "https://example.com/article")

    @contextmanager
    def _db_context():
        yield db_session

    monkeypatch.setattr(stp, "get_db", _db_context)

    class DummyHttpService:
        def fetch_content(self, url):  # noqa: ANN001
            html = (
                '<link rel="alternate" type="application/rss+xml" '
                'href="https://example.com/feed" title="Example Feed" />'
            )
            return f"<html><head>{html}</head><body></body></html>", {}

    monkeypatch.setattr(stp, "get_http_service", lambda: DummyHttpService())
    monkeypatch.setattr(
        stp,
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
    monkeypatch.setattr(stp, "subscribe_to_detected_feed", subscribe_mock)
    monkeypatch.setattr(stp, "get_content_analyzer", Mock())

    processor = stp.SequentialTaskProcessor()
    processor.queue_service.enqueue = Mock()

    task_data = {
        "task_type": stp.TaskType.ANALYZE_URL.value,
        "payload": {"content_id": content.id, "subscribe_to_feed": True},
    }

    assert processor._process_analyze_url_task(task_data) is True
    processor.queue_service.enqueue.assert_not_called()

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

    @contextmanager
    def _db_context():
        yield db_session

    monkeypatch.setattr(stp, "get_db", _db_context)
    monkeypatch.setattr(stp, "get_llm_service", lambda: None)

    monkeypatch.setattr(
        stp,
        "resolve_twitter_credentials",
        lambda: TwitterCredentialsResult(
            success=True,
            credentials=TwitterCredentials(auth_token="auth", ct0="ct0", user_agent="ua"),
        ),
    )
    monkeypatch.setattr(
        stp,
        "fetch_tweet_detail",
        lambda params: _build_tweet_fetch_result(
            ["https://example.com/a", "https://example.com/b"]
        ),
    )

    processor = stp.SequentialTaskProcessor()
    processor.queue_service.enqueue = Mock()

    task_data = {
        "task_type": stp.TaskType.ANALYZE_URL.value,
        "payload": {"content_id": content.id},
    }

    assert processor._process_analyze_url_task(task_data) is True

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

    @contextmanager
    def _db_context():
        yield db_session

    monkeypatch.setattr(stp, "get_db", _db_context)
    monkeypatch.setattr(stp, "get_llm_service", lambda: None)

    monkeypatch.setattr(
        stp,
        "resolve_twitter_credentials",
        lambda: TwitterCredentialsResult(
            success=True,
            credentials=TwitterCredentials(auth_token="auth", ct0="ct0", user_agent="ua"),
        ),
    )
    monkeypatch.setattr(stp, "fetch_tweet_detail", lambda params: _build_tweet_fetch_result([]))

    processor = stp.SequentialTaskProcessor()
    processor.queue_service.enqueue = Mock()

    task_data = {
        "task_type": stp.TaskType.ANALYZE_URL.value,
        "payload": {"content_id": content.id},
    }

    assert processor._process_analyze_url_task(task_data) is True

    updated = db_session.query(Content).filter(Content.id == content.id).first()
    assert updated is not None
    assert updated.url == "https://x.com/i/status/123"
    assert updated.content_metadata.get("tweet_only") is True
    assert updated.content_metadata.get("tweet_thread_text") == "Main tweet\n\nThread follow-up"
