"""Tests for fetch discussion task handler."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import Mock

from app.pipeline.handlers.fetch_discussion import FetchDiscussionHandler
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope
from app.services.discussion_fetcher import DiscussionFetchResult
from app.services.queue import TaskType


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


def test_handler_returns_non_retryable_when_content_id_missing(db_session) -> None:
    handler = FetchDiscussionHandler()
    context = _build_context(db_session)
    task = TaskEnvelope(id=1, task_type=TaskType.FETCH_DISCUSSION, payload={})

    result = handler.handle(task, context)

    assert result.success is False
    assert result.retryable is False


def test_handler_returns_ok_on_success(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.pipeline.handlers.fetch_discussion.fetch_and_store_discussion",
        lambda _db, content_id: DiscussionFetchResult(
            success=True,
            status="completed",
            error_message=None,
            retryable=False,
        ),
    )

    handler = FetchDiscussionHandler()
    context = _build_context(db_session)
    task = TaskEnvelope(id=2, task_type=TaskType.FETCH_DISCUSSION, content_id=123)

    result = handler.handle(task, context)

    assert result.success is True


def test_handler_propagates_retryability_on_failure(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.pipeline.handlers.fetch_discussion.fetch_and_store_discussion",
        lambda _db, content_id: DiscussionFetchResult(
            success=False,
            status="failed",
            error_message="timed out",
            retryable=True,
        ),
    )

    handler = FetchDiscussionHandler()
    context = _build_context(db_session)
    task = TaskEnvelope(id=3, task_type=TaskType.FETCH_DISCUSSION, content_id=123)

    result = handler.handle(task, context)

    assert result.success is False
    assert result.retryable is True
    assert result.error_message == "timed out"
