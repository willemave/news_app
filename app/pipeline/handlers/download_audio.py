"""Podcast audio download task handler."""

from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.podcast_workers import PodcastDownloadWorker
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.services.queue import TaskType

logger = get_logger(__name__)


class DownloadAudioHandler:
    """Handle podcast audio download tasks."""

    task_type = TaskType.DOWNLOAD_AUDIO

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Download audio files for podcast content."""
        try:
            content_id = task.content_id or task.payload.get("content_id")
            if not content_id:
                logger.error("No content_id provided for download task")
                return TaskResult.fail("No content_id provided")

            worker = PodcastDownloadWorker()
            success = worker.process_download_task(int(content_id))
            return TaskResult.ok() if success else TaskResult.fail()
        except Exception as exc:  # noqa: BLE001
            logger.error("Download error: %s", exc, exc_info=True)
            return TaskResult.fail(str(exc))
