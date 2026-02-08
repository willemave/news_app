"""Tests for summarize task routing."""

from contextlib import contextmanager
from unittest.mock import Mock

from app.constants import SUMMARY_KIND_LONG_EDITORIAL_NARRATIVE, SUMMARY_VERSION_V1
from app.models.metadata import EditorialNarrativeSummary, NewsSummary
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
        return EditorialNarrativeSummary(
            title="Article Title",
            editorial_narrative=(
                "First paragraph with concrete details, entities, metrics, and a clear thesis "
                "about why execution quality, governance controls, and measurable impact matter "
                "more than isolated benchmark gains.\n\n"
                "Second paragraph with implications, constraints, and evidence-driven guidance "
                "that outlines near-term tradeoffs, implementation risks, and practical actions."
            ),
            quotes=[
                {"text": "Quote one with enough detail for validation.", "attribution": "Source A"},
                {"text": "Quote two with enough detail for validation.", "attribution": "Source B"},
            ],
            key_points=[
                {"point": "Key point one with concrete detail and consequence."},
                {"point": "Key point two with concrete detail and consequence."},
                {"point": "Key point three with concrete detail and consequence."},
                {"point": "Key point four with concrete detail and consequence."},
            ],
        )


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
    db_session.refresh(content)
    assert content.content_metadata["summary_kind"] == SUMMARY_KIND_LONG_EDITORIAL_NARRATIVE
    assert content.content_metadata["summary_version"] == SUMMARY_VERSION_V1


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
