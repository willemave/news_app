"""Discussion fetch task handler."""

from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.services.discussion_fetcher import fetch_and_store_discussion
from app.services.queue import TaskType

logger = get_logger(__name__)


class FetchDiscussionHandler:
    """Handle discussion ingestion tasks for news content."""

    task_type = TaskType.FETCH_DISCUSSION

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Fetch and persist discussion payload for a content item."""
        content_id = task.content_id or task.payload.get("content_id")
        if content_id is None:
            logger.error(
                "No content_id provided for fetch_discussion task",
                extra={
                    "component": "fetch_discussion",
                    "operation": "load_task",
                    "item_id": None,
                    "context_data": {"task_data": task.model_dump()},
                },
            )
            return TaskResult.fail("No content_id provided", retryable=False)

        content_id = int(content_id)

        try:
            with context.db_factory() as db:
                result = fetch_and_store_discussion(db, content_id=content_id)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Discussion fetch handler failed for content %s",
                content_id,
                extra={
                    "component": "fetch_discussion",
                    "operation": "handle",
                    "item_id": str(content_id),
                    "context_data": {"error": str(exc)},
                },
            )
            return TaskResult.fail(str(exc), retryable=True)

        if result.success:
            return TaskResult.ok()

        return TaskResult.fail(
            result.error_message or "Discussion fetch failed",
            retryable=result.retryable,
        )
