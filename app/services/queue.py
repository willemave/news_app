from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import and_, func, or_

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.schema import ProcessingTask

logger = get_logger(__name__)


class TaskType(StrEnum):
    SCRAPE = "scrape"
    ANALYZE_URL = "analyze_url"  # Analyze URL to determine content type
    PROCESS_CONTENT = "process_content"
    DOWNLOAD_AUDIO = "download_audio"
    TRANSCRIBE = "transcribe"
    SUMMARIZE = "summarize"
    GENERATE_IMAGE = "generate_image"
    DISCOVER_FEEDS = "discover_feeds"
    ONBOARDING_DISCOVER = "onboarding_discover"
    DIG_DEEPER = "dig_deeper"


class TaskQueue(StrEnum):
    CONTENT = "content"
    TRANSCRIBE = "transcribe"
    ONBOARDING = "onboarding"
    CHAT = "chat"


TASK_QUEUE_BY_TYPE: dict[TaskType, TaskQueue] = {
    TaskType.SCRAPE: TaskQueue.CONTENT,
    TaskType.ANALYZE_URL: TaskQueue.CONTENT,
    TaskType.PROCESS_CONTENT: TaskQueue.CONTENT,
    TaskType.DOWNLOAD_AUDIO: TaskQueue.CONTENT,
    TaskType.TRANSCRIBE: TaskQueue.TRANSCRIBE,
    TaskType.SUMMARIZE: TaskQueue.CONTENT,
    TaskType.GENERATE_IMAGE: TaskQueue.CONTENT,
    TaskType.DISCOVER_FEEDS: TaskQueue.CONTENT,
    TaskType.ONBOARDING_DISCOVER: TaskQueue.ONBOARDING,
    TaskType.DIG_DEEPER: TaskQueue.CHAT,
}

DEDUPABLE_CONTENT_TASK_TYPES: set[TaskType] = {
    TaskType.PROCESS_CONTENT,
    TaskType.SUMMARIZE,
    TaskType.GENERATE_IMAGE,
}


class TaskStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class QueueService:
    """Simple database-backed task queue."""

    @staticmethod
    def _normalize_queue_name(
        queue_name: TaskQueue | str | None,
    ) -> str | None:
        """Normalize queue names for DB filtering."""
        if queue_name is None:
            return None
        if isinstance(queue_name, TaskQueue):
            return queue_name.value
        return TaskQueue(queue_name).value

    @staticmethod
    def _resolve_task_queue(
        task_type: TaskType,
        queue_name: TaskQueue | str | None = None,
    ) -> str:
        """Resolve the target queue for a task enqueue."""
        normalized = QueueService._normalize_queue_name(queue_name)
        if normalized:
            return normalized
        return TASK_QUEUE_BY_TYPE[task_type].value

    def enqueue(
        self,
        task_type: TaskType,
        content_id: int | None = None,
        payload: dict[str, Any] | None = None,
        queue_name: TaskQueue | str | None = None,
        dedupe: bool | None = None,
    ) -> int:
        """
        Add a task to the queue.

        Returns:
            Task ID
        """
        target_queue = self._resolve_task_queue(task_type, queue_name)
        with get_db() as db:
            should_dedupe = (
                dedupe if dedupe is not None else task_type in DEDUPABLE_CONTENT_TASK_TYPES
            )
            if should_dedupe and content_id is not None:
                existing_task = (
                    db.query(ProcessingTask)
                    .filter(ProcessingTask.task_type == task_type.value)
                    .filter(ProcessingTask.content_id == content_id)
                    .filter(ProcessingTask.queue_name == target_queue)
                    .filter(
                        ProcessingTask.status.in_(
                            [TaskStatus.PENDING.value, TaskStatus.PROCESSING.value]
                        )
                    )
                    .order_by(ProcessingTask.created_at.desc())
                    .first()
                )
                if existing_task:
                    logger.info(
                        "Reusing existing task %s of type %s for content %s (queue=%s)",
                        existing_task.id,
                        task_type.value,
                        content_id,
                        target_queue,
                    )
                    return existing_task.id

            task = ProcessingTask(
                task_type=task_type.value,
                content_id=content_id,
                payload=payload or {},
                status=TaskStatus.PENDING.value,
                queue_name=target_queue,
            )
            db.add(task)
            db.commit()
            db.refresh(task)

            logger.info(
                "Enqueued task %s of type %s (queue=%s)",
                task.id,
                task_type.value,
                target_queue,
            )
            return task.id

    def dequeue(
        self,
        task_type: TaskType | None = None,
        worker_id: str = "worker",
        queue_name: TaskQueue | str | None = None,
    ) -> dict[str, Any] | None:
        """
        Get the next available task from the queue.

        Args:
            task_type: Filter by task type (optional)
            worker_id: ID of the worker claiming the task
            queue_name: Filter by queue partition (optional)

        Returns:
            Task data as dictionary or None if queue is empty
        """
        with get_db() as db:
            # Retry claim a few times to avoid races across worker processes.
            # This compare-and-set pattern works reliably even where SKIP LOCKED
            # semantics are unavailable (e.g., SQLite).
            for _ in range(5):
                now = datetime.now(UTC)
                query = db.query(ProcessingTask.id).filter(
                    ProcessingTask.status == TaskStatus.PENDING.value,
                    or_(ProcessingTask.created_at.is_(None), ProcessingTask.created_at <= now),
                )

                if task_type:
                    query = query.filter(ProcessingTask.task_type == task_type.value)

                normalized_queue = self._normalize_queue_name(queue_name)
                if normalized_queue:
                    query = query.filter(ProcessingTask.queue_name == normalized_queue)

                # Order by retry priority and schedule time.
                task_row = query.order_by(
                    ProcessingTask.retry_count,
                    ProcessingTask.created_at,
                ).first()
                if task_row is None:
                    return None

                task_id = int(task_row[0])
                claimed = (
                    db.query(ProcessingTask)
                    .filter(
                        ProcessingTask.id == task_id,
                        ProcessingTask.status == TaskStatus.PENDING.value,
                    )
                    .update(
                        {
                            ProcessingTask.status: TaskStatus.PROCESSING.value,
                            ProcessingTask.started_at: now,
                        },
                        synchronize_session=False,
                    )
                )
                if claimed == 0:
                    db.rollback()
                    continue
                db.commit()

                task = db.query(ProcessingTask).filter(ProcessingTask.id == task_id).first()
                if task is None:
                    return None

                # Create a dictionary with all necessary task data
                # This prevents "not bound to Session" errors
                task_data = {
                    "id": task.id,
                    "task_type": task.task_type,
                    "content_id": task.content_id,
                    "payload": task.payload,
                    "retry_count": task.retry_count,
                    "status": task.status,
                    "queue_name": task.queue_name,
                    "created_at": task.created_at,
                    "started_at": task.started_at,
                }

                logger.debug(
                    "Dequeued task %s for %s (queue=%s)",
                    task_data["id"],
                    worker_id,
                    task_data["queue_name"],
                )
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
                if not error_message:
                    error_message = "Task failed without error details"
                task.status = TaskStatus.FAILED.value
                task.error_message = error_message
                logger.error(
                    f"Task {task_id} failed: {error_message}",
                    extra={
                        "component": "app.services.queue",
                        "operation": "complete_task",
                        "item_id": task_id,
                        "context_data": {"error_message": error_message},
                    },
                )

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

            queue_counts = (
                db.query(ProcessingTask.queue_name, func.count(ProcessingTask.id))
                .filter(ProcessingTask.status == TaskStatus.PENDING.value)
                .group_by(ProcessingTask.queue_name)
                .all()
            )
            stats["pending_by_queue"] = {queue_name: count for queue_name, count in queue_counts}

            queue_type_counts = (
                db.query(
                    ProcessingTask.queue_name,
                    ProcessingTask.task_type,
                    func.count(ProcessingTask.id),
                )
                .filter(ProcessingTask.status == TaskStatus.PENDING.value)
                .group_by(ProcessingTask.queue_name, ProcessingTask.task_type)
                .all()
            )
            pending_by_queue_type: dict[str, dict[str, int]] = {}
            for queue_name, task_type, count in queue_type_counts:
                if queue_name not in pending_by_queue_type:
                    pending_by_queue_type[queue_name] = {}
                pending_by_queue_type[queue_name][task_type] = count
            stats["pending_by_queue_type"] = pending_by_queue_type

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
