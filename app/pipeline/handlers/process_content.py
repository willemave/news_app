"""Content processing task handler."""

from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.pipeline.worker import ContentWorker
from app.services.queue import TaskType

logger = get_logger(__name__)


class ProcessContentHandler:
    """Handle content processing tasks."""

    task_type = TaskType.PROCESS_CONTENT

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Process content with registered strategies."""
        try:
            content_id = task.content_id
            if content_id is None:
                content_id = task.payload.get("content_id")

            if content_id is None:
                logger.error("No content_id found in task data: %s", task.model_dump())
                return TaskResult.fail("No content_id provided")

            content_id = int(content_id)
            logger.info("Processing content %s", content_id)

            worker = ContentWorker()
            success = worker.process_content(content_id, context.worker_id)

            if success:
                logger.info("Content %s processed successfully", content_id)
                return TaskResult.ok()

            logger.error("Content %s processing failed", content_id)
            return TaskResult.fail()
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "Content processing error for content_id %s: %s",
                content_id if "content_id" in locals() else "unknown",
                exc,
                exc_info=True,
            )
            logger.error("Full task data: %s", task.model_dump())
            return TaskResult.fail(str(exc))
