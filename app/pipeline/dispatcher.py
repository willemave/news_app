"""Dispatcher for routing tasks to handlers."""

from __future__ import annotations

from collections.abc import Iterable

from app.core.logging import get_logger
from app.pipeline.task_context import TaskContext
from app.pipeline.task_handler import TaskHandler
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.services.queue import TaskType

logger = get_logger(__name__)


class TaskDispatcher:
    """Route tasks to the appropriate handler."""

    def __init__(self, handlers: Iterable[TaskHandler]) -> None:
        self._handlers: dict[TaskType, TaskHandler] = {}
        for handler in handlers:
            if handler.task_type in self._handlers:
                raise ValueError(f"Duplicate handler for task type {handler.task_type}")
            self._handlers[handler.task_type] = handler

    def dispatch(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Dispatch a task to its handler."""
        handler = self._handlers.get(task.task_type)
        if not handler:
            logger.error(
                "Unknown task type: %s",
                task.task_type,
                extra={
                    "component": "task_dispatcher",
                    "operation": "dispatch",
                    "item_id": task.id,
                    "context_data": {"task_type": task.task_type.value},
                },
            )
            return TaskResult.fail(f"Unknown task type: {task.task_type.value}")
        return handler.handle(task, context)
