"""Tests for summarize task routing."""

from contextlib import contextmanager
from unittest.mock import Mock

from app.models.metadata import NewsSummary
from app.models.schema import Content
from app.pipeline.handlers.summarize import SummarizeHandler
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope
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


def _build_context(db_session, queue_service, llm_service) -> TaskContext:
    return TaskContext(
        queue_service=queue_service,
        settings=Mock(),
        llm_service=llm_service,
        worker_id="test-worker",
        db_factory=_override_get_db(db_session),
    )


def test_summarize_news_does_not_enqueue_image_tasks(db_session) -> None:
    content = _create_content(db_session, "news")
    queue_service = Mock()
    handler = SummarizeHandler()
    context = _build_context(db_session, queue_service, DummySummarizer())

    task = TaskEnvelope(
        id=1,
        task_type=TaskType.SUMMARIZE,
        content_id=content.id,
    )

    assert handler.handle(task, context).success is True
    queue_service.enqueue.assert_not_called()


def test_summarize_article_enqueues_image(db_session) -> None:
    content = _create_content(db_session, "article")
    queue_service = Mock()
    handler = SummarizeHandler()
    context = _build_context(db_session, queue_service, DummySummarizer())

    task = TaskEnvelope(
        id=2,
        task_type=TaskType.SUMMARIZE,
        content_id=content.id,
    )

    assert handler.handle(task, context).success is True
    queue_service.enqueue.assert_called_once_with(
        task_type=TaskType.GENERATE_IMAGE,
        content_id=content.id,
    )


def test_summarize_article_falls_back_to_content_to_summarize(db_session) -> None:
    content = Content(
        content_type="article",
        url="https://example.com/fallback",
        status="processing",
        content_metadata={"content": "", "content_to_summarize": "Fallback content"},
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)

    queue_service = Mock()
    llm_service = Mock()
    llm_service.summarize_content.return_value = {
        "title": "Article Title",
        "overview": "Summary",
        "bullet_points": [],
    }
    handler = SummarizeHandler()
    context = _build_context(db_session, queue_service, llm_service)

    task = TaskEnvelope(
        id=3,
        task_type=TaskType.SUMMARIZE,
        content_id=content.id,
    )

    assert handler.handle(task, context).success is True
    llm_service.summarize_content.assert_called_once()
    assert llm_service.summarize_content.call_args[0][0] == "Fallback content"
