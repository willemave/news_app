"""Scrape task handler."""

from __future__ import annotations

from app.core.logging import get_logger
from app.pipeline.task_context import TaskContext
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.scraping.runner import ScraperRunner
from app.services.queue import TaskType

logger = get_logger(__name__)


class ScrapeHandler:
    """Handle scrape tasks."""

    task_type = TaskType.SCRAPE

    def handle(self, task: TaskEnvelope, context: TaskContext) -> TaskResult:
        """Run configured scrapers."""
        try:
            payload = task.payload or {}
            sources = payload.get("sources", ["all"])
            runner = ScraperRunner()

            if sources == ["all"]:
                runner.run_all()
            else:
                for source in sources:
                    runner.run_scraper(source)
            return TaskResult.ok()
        except Exception as exc:  # noqa: BLE001
            logger.error("Scraper error: %s", exc, exc_info=True)
            return TaskResult.fail(str(exc))
