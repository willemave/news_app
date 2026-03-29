"""Task handler for news-native digest generation."""

from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.services.news_digests import generate_news_digest_for_user
from app.services.queue import TaskType

logger = get_logger(__name__)


class GenerateNewsDigestHandler:
    """Handle queued news digest generation tasks."""

    task_type = TaskType.GENERATE_NEWS_DIGEST

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        payload = task.payload if isinstance(task.payload, dict) else {}
        raw_user_id = payload.get("user_id")
        trigger_reason = payload.get("trigger_reason")
        force = bool(payload.get("force", False))

        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            return TaskResult.fail("Invalid user_id in digest task payload", retryable=False)

        try:
            with context.db_factory() as db:
                result = generate_news_digest_for_user(
                    db,
                    user_id=user_id,
                    trigger_reason=trigger_reason if isinstance(trigger_reason, str) else None,
                    force=force,
                )
            if result.skipped:
                return TaskResult.ok()
            return TaskResult.ok()
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "News digest generation failed",
                extra={
                    "component": "generate_news_digest",
                    "operation": "handle",
                    "item_id": str(user_id),
                    "context_data": {"task_id": task.id, "trigger_reason": trigger_reason},
                },
            )
            return TaskResult.fail(str(exc))
