"""Tests for summarize task routing."""

from contextlib import contextmanager

from app.models.metadata import NewsSummary
from app.models.schema import Content
from app.pipeline.sequential_task_processor import SequentialTaskProcessor
from app.services.queue import TaskType


def _override_get_db(db_session):
    @contextmanager
    def _get_db():
        yield db_session

    return _get_db


class DummySummarizer:
    """Minimal summarizer stub for task routing tests."""

    def summarize_content(
        self,
        content: str,
        content_type: str,
        content_id: int,
        max_bullet_points: int,
        max_quotes: int,
        provider_override: str | None = None,
    ):
        if content_type == "news_digest":
            return NewsSummary(
                title="News Title",
                article_url="https://example.com",
                key_points=["Point 1"],
                summary="Overview",
            )
        return {"title": "Article Title", "overview": "Summary", "bullet_points": []}


def _create_content(db_session, content_type: str) -> Content:
    content = Content(
        content_type=content_type,
        url="https://example.com",
        status="processing",
        content_metadata={
            "content": "Some content",
            "article": {"url": "https://example.com"},
        }
        if content_type == "news"
        else {"content": "Some content"},
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def test_summarize_news_enqueues_thumbnail(db_session, monkeypatch) -> None:
    content = _create_content(db_session, "news")
    processor = SequentialTaskProcessor()
    processor.llm_service = DummySummarizer()

    enqueued = []

    monkeypatch.setattr(processor.queue_service, "enqueue", lambda task_type, **_: enqueued.append(task_type))
    monkeypatch.setattr(
        "app.pipeline.sequential_task_processor.get_db",
        _override_get_db(db_session),
    )

    assert processor._process_summarize_task({"content_id": content.id}) is True
    assert enqueued == [TaskType.GENERATE_THUMBNAIL]


def test_summarize_article_enqueues_image(db_session, monkeypatch) -> None:
    content = _create_content(db_session, "article")
    processor = SequentialTaskProcessor()
    processor.llm_service = DummySummarizer()

    enqueued = []

    monkeypatch.setattr(processor.queue_service, "enqueue", lambda task_type, **_: enqueued.append(task_type))
    monkeypatch.setattr(
        "app.pipeline.sequential_task_processor.get_db",
        _override_get_db(db_session),
    )

    assert processor._process_summarize_task({"content_id": content.id}) is True
    assert enqueued == [TaskType.GENERATE_IMAGE]
