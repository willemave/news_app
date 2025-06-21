from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from sqlalchemy import and_, func

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.schema import ProcessingTask

logger = get_logger(__name__)


class TaskType(str, Enum):
    SCRAPE = "scrape"
    PROCESS_CONTENT = "process_content"
    DOWNLOAD_AUDIO = "download_audio"
    TRANSCRIBE = "transcribe"
    SUMMARIZE = "summarize"


class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class QueueService:
    """Simple database-backed task queue."""

    def enqueue(
        self,
        task_type: TaskType,
        content_id: int | None = None,
        payload: dict[str, Any] | None = None,
    ) -> int:
        """
        Add a task to the queue.

        Returns:
            Task ID
        """
        with get_db() as db:
            task = ProcessingTask(
                task_type=task_type.value,
                content_id=content_id,
                payload=payload or {},
                status=TaskStatus.PENDING.value,
            )
            db.add(task)
            db.commit()
            db.refresh(task)

            logger.info(f"Enqueued task {task.id} of type {task_type}")
            return task.id

    def dequeue(
        self, task_type: TaskType | None = None, worker_id: str = "worker"
    ) -> dict[str, Any] | None:
        """
        Get the next available task from the queue.

        Args:
            task_type: Filter by task type (optional)
            worker_id: ID of the worker claiming the task

        Returns:
            Task data as dictionary or None if queue is empty
        """
        with get_db() as db:
            # Build query
            query = db.query(ProcessingTask).filter(
                ProcessingTask.status == TaskStatus.PENDING.value
            )

            if task_type:
                query = query.filter(ProcessingTask.task_type == task_type.value)

            # Order by priority (retry_count) and creation time
            query = query.order_by(ProcessingTask.retry_count, ProcessingTask.created_at)

            # Lock the row for update
            task = query.with_for_update(skip_locked=True).first()

            if task:
                task.status = TaskStatus.PROCESSING.value
                task.started_at = datetime.now(UTC)
                db.commit()

                # Create a dictionary with all necessary task data
                # This prevents "not bound to Session" errors
                task_data = {
                    "id": task.id,
                    "task_type": task.task_type,
                    "content_id": task.content_id,
                    "payload": task.payload,
                    "retry_count": task.retry_count,
                    "status": task.status,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                }

                logger.debug(f"Dequeued task {task_data['id']} for {worker_id}")

                return task_data

            return None

    def complete_task(self, task_id: int, success: bool = True, error_message: str | None = None):
        """Mark a task as completed."""
        with get_db() as db:
            task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()

            if not task:
                logger.error(f"Task {task_id} not found")
                return

            task.completed_at = datetime.now(UTC)

            if success:
                task.status = TaskStatus.COMPLETED.value
                logger.info(f"Task {task_id} completed successfully")
            else:
                task.status = TaskStatus.FAILED.value
                task.error_message = error_message
                logger.error(f"Task {task_id} failed: {error_message}")

            db.commit()

    def retry_task(self, task_id: int, delay_seconds: int = 60):
        """Retry a failed task after a delay."""
        with get_db() as db:
            task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()

            if not task:
                logger.error(f"Task {task_id} not found")
                return

            task.status = TaskStatus.PENDING.value
            task.retry_count += 1
            task.started_at = None
            task.completed_at = None

            # Set a future created_at to delay processing
            task.created_at = datetime.now(UTC) + timedelta(seconds=delay_seconds)

            db.commit()
            logger.info(f"Task {task_id} scheduled for retry (attempt {task.retry_count})")

    def get_queue_stats(self) -> dict[str, Any]:
        """Get queue statistics."""
        with get_db() as db:
            stats = {}

            # Count by status
            status_counts = (
                db.query(ProcessingTask.status, func.count(ProcessingTask.id))
                .group_by(ProcessingTask.status)
                .all()
            )

            stats["by_status"] = {status: count for status, count in status_counts}

            # Count by type
            type_counts = (
                db.query(ProcessingTask.task_type, func.count(ProcessingTask.id))
                .filter(ProcessingTask.status == TaskStatus.PENDING.value)
                .group_by(ProcessingTask.task_type)
                .all()
            )

            stats["pending_by_type"] = {task_type: count for task_type, count in type_counts}

            # Failed tasks in last hour
            one_hour_ago = datetime.now(UTC) - timedelta(hours=1)
            recent_failures = (
                db.query(func.count(ProcessingTask.id))
                .filter(
                    and_(
                        ProcessingTask.status == TaskStatus.FAILED.value,
                        ProcessingTask.completed_at >= one_hour_ago,
                    )
                )
                .scalar()
            )

            stats["recent_failures"] = recent_failures

            return stats

    def cleanup_old_tasks(self, days: int = 7):
        """Remove completed tasks older than specified days."""
        with get_db() as db:
            cutoff_date = datetime.now(UTC) - timedelta(days=days)

            deleted = (
                db.query(ProcessingTask)
                .filter(
                    and_(
                        ProcessingTask.status == TaskStatus.COMPLETED.value,
                        ProcessingTask.completed_at < cutoff_date,
                    )
                )
                .delete()
            )

            db.commit()
            logger.info(f"Cleaned up {deleted} old completed tasks")


# Global instance
_queue_service = None


def get_queue_service() -> QueueService:
    """Get the global queue service instance."""
    global _queue_service
    if _queue_service is None:
        _queue_service = QueueService()
    return _queue_service
