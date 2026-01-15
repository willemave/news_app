"""Handler protocol and adapters for task processing."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.services.queue import TaskType


class TaskHandler(Protocol):
    """Protocol for task handlers."""

    task_type: TaskType

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Handle a task and return a TaskResult."""


class FunctionTaskHandler:
    """Adapter for function-based task handling."""

    def __init__(
        self,
        task_type: TaskType,
        handler: Callable[[TaskEnvelope, TaskContext], TaskResult],
    ) -> None:
        self.task_type = task_type
        self._handler = handler

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Delegate task handling to the provided callable."""
        return self._handler(task, context)
