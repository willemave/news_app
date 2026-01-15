"""Thumbnail generation task handler."""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.logging import get_logger
from app.models.schema import Content
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.services.queue import TaskType

logger = get_logger(__name__)


class GenerateThumbnailHandler:
    """Handle screenshot-based thumbnail generation for news content."""

    task_type = TaskType.GENERATE_THUMBNAIL

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Generate a screenshot-based thumbnail."""
        try:
            content_id = task.content_id or task.payload.get("content_id")
            if not content_id:
                logger.error("No content_id provided for thumbnail generation task")
                return TaskResult.fail("No content_id provided")

            content_id = int(content_id)
            logger.info("Generating thumbnail for content %s", content_id)

            from app.services.news_thumbnail_screenshot import (
                NewsThumbnailJob,
                generate_news_thumbnail,
            )

            result = generate_news_thumbnail(NewsThumbnailJob(content_id=content_id))

            if result.success:
                if result.error_message and "Skipped" in result.error_message:
                    logger.info(
                        "Thumbnail generation skipped for %s: %s",
                        content_id,
                        result.error_message,
                    )
                    return TaskResult.ok()
                with context.db_factory() as db:
                    content = db.query(Content).filter(Content.id == content_id).first()
                    if not content:
                        logger.error(
                            "Content %s not found for thumbnail metadata update",
                            content_id,
                        )
                        return TaskResult.fail("Content not found")
                    from app.utils.image_urls import (
                        build_news_thumbnail_url,
                        build_thumbnail_url,
                    )

                    metadata = dict(content.content_metadata or {})
                    metadata["image_generated_at"] = datetime.now(UTC).isoformat()
                    metadata["image_url"] = build_news_thumbnail_url(content_id)
                    if result.thumbnail_path:
                        metadata["thumbnail_url"] = build_thumbnail_url(content_id)
                    content.content_metadata = metadata
                    db.commit()

                logger.info(
                    "Successfully generated thumbnail for content %s at %s",
                    content_id,
                    result.image_path,
                )
                return TaskResult.ok()

            logger.error(
                "Thumbnail generation failed for %s: %s",
                content_id,
                result.error_message,
                extra={
                    "component": "thumbnail_generation",
                    "operation": "generate_thumbnail",
                    "item_id": content_id,
                },
            )
            return TaskResult.fail(result.error_message)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Thumbnail generation task failed",
                extra={
                    "component": "thumbnail_generation",
                    "operation": "generate_thumbnail_task",
                    "item_id": str(task.content_id or task.payload.get("content_id") or "unknown"),
                    "context_data": {"error": str(exc)},
                },
            )
            return TaskResult.fail(str(exc))
