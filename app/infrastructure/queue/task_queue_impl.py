"""Infrastructure implementation helpers for the task queue gateway."""

from __future__ import annotations

from app.services.queue import QueueService


def build_task_queue_service() -> QueueService:
    """Build the concrete queue service used behind TaskQueueGateway."""
    return QueueService()
