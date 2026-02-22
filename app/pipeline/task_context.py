"""Shared dependencies for task handlers."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.settings import Settings
from app.services.gateways.task_queue_gateway import TaskQueueGateway
from app.services.queue import QueueService


@dataclass(frozen=True)
class TaskContext:
    """Container for shared task processing dependencies."""

    queue_service: QueueService
    settings: Settings
    llm_service: Any
    worker_id: str
    queue_gateway: TaskQueueGateway | None = None
    db_factory: Callable[[], AbstractContextManager[Session]] = get_db

    @property
    def queue(self) -> TaskQueueGateway:
        """Return canonical queue gateway for handlers/workflows."""
        if self.queue_gateway is not None:
            return self.queue_gateway
        return TaskQueueGateway(queue_service=self.queue_service)
