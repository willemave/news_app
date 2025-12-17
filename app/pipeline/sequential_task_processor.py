"""Sequential task processor for robust, simple task processing."""

import signal
import sys
import time
from datetime import UTC, datetime
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.core.settings import get_settings
from app.models.metadata import ContentStatus, NewsSummary
from app.models.schema import Content
from app.pipeline.podcast_workers import PodcastDownloadWorker, PodcastTranscribeWorker
from app.pipeline.worker import ContentWorker, get_llm_service
from app.scraping.runner import ScraperRunner
from app.services.queue import QueueService, TaskType
from app.utils.error_logger import log_processing_error

logger = get_logger(__name__)


class SequentialTaskProcessor:
    """Sequential task processor - processes tasks one at a time."""

    def __init__(self):
        logger.debug("Initializing SequentialTaskProcessor...")
        self.queue_service = QueueService()
        logger.debug("QueueService initialized")
        self.llm_service = get_llm_service()
        logger.debug("Shared summarization service initialized")
        self.settings = get_settings()
        logger.debug("Settings loaded")
        self.running = True
        self.worker_id = "sequential-processor"
        logger.debug(f"SequentialTaskProcessor initialized with worker_id: {self.worker_id}")

    def process_task(self, task_data: dict[str, Any]) -> bool:
        """Process a single task."""
        task_id = task_data.get("id", "unknown")
        start_time = time.time()

        try:
            task_type = TaskType(task_data["task_type"])
            logger.info(f"Processing task {task_id} of type {task_type}")
            logger.debug(f"Task {task_id} data: {task_data}")

            result = False
            if task_type == TaskType.SCRAPE:
                result = self._process_scrape_task(task_data)
            elif task_type == TaskType.PROCESS_CONTENT:
                result = self._process_content_task(task_data)
            elif task_type == TaskType.DOWNLOAD_AUDIO:
                result = self._process_download_task(task_data)
            elif task_type == TaskType.TRANSCRIBE:
                result = self._process_transcribe_task(task_data)
            elif task_type == TaskType.SUMMARIZE:
                result = self._process_summarize_task(task_data)
            else:
                logger.error(f"Unknown task type: {task_type}")
                result = False

            elapsed = time.time() - start_time
            logger.info(f"Task {task_id} completed in {elapsed:.2f}s with result: {result}")
            return result

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(
                f"Error processing task {task_id} after {elapsed:.2f}s: {e}", exc_info=True
            )
            return False

    def _process_scrape_task(self, task_data: dict[str, Any]) -> bool:
        """Process a scrape task."""
        try:
            payload = task_data.get("payload", {})
            sources = payload.get("sources", ["all"])
            runner = ScraperRunner()

            # Run scrapers
            if sources == ["all"]:
                runner.run_all()
            else:
                for source in sources:
                    runner.run_scraper(source)
            return True
        except Exception as e:
            logger.error(f"Scraper error: {e}", exc_info=True)
            return False

    def _process_content_task(self, task_data: dict[str, Any]) -> bool:
        """Process content with strategies."""
        try:
            # Try to get content_id from top level first, then from payload
            content_id = task_data.get("content_id")
            if content_id is None:
                content_id = task_data.get("payload", {}).get("content_id")

            if content_id is None:
                logger.error(f"No content_id found in task data: {task_data}")
                return False

            content_id = int(content_id)
            logger.info(f"Processing content {content_id}")

            worker = ContentWorker()
            success = worker.process_content(content_id, self.worker_id)

            if success:
                logger.info(f"Content {content_id} processed successfully")
                return True
            else:
                logger.error(f"Content {content_id} processing failed")
                return False
        except Exception as e:
            logger.error(
                f"Content processing error for content_id {content_id}: {e}", exc_info=True
            )
            logger.error(f"Full task data: {task_data}")
            return False

    def _process_download_task(self, task_data: dict[str, Any]) -> bool:
        """Download audio files."""
        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )
            if not content_id:
                logger.error("No content_id provided for download task")
                return False

            worker = PodcastDownloadWorker()
            return worker.process_download_task(content_id)
        except Exception as e:
            logger.error(f"Download error: {e}", exc_info=True)
            return False

    def _process_transcribe_task(self, task_data: dict[str, Any]) -> bool:
        """Transcribe audio files."""
        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )
            if not content_id:
                logger.error("No content_id provided for transcribe task")
                return False

            worker = PodcastTranscribeWorker()
            return worker.process_transcribe_task(content_id)
        except Exception as e:
            logger.error(f"Transcription error: {e}", exc_info=True)
            return False

    def _process_summarize_task(self, task_data: dict[str, Any]) -> bool:
        """Generate content summaries."""
        try:
            content_id = task_data.get("content_id") or task_data.get("payload", {}).get(
                "content_id"
            )

            if not content_id:
                logger.error(
                    "SUMMARIZE_TASK_ERROR: No content_id provided. Task data: %s",
                    task_data,
                )
                return False

            logger.info("Processing summarize task for content %s", content_id)

            # Get content from database
            with get_db() as db:
                content = db.query(Content).filter(Content.id == content_id).first()
                if not content:
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: Content %s not found in database",
                        content_id,
                    )
                    return False

                # Log content details for debugging
                title_preview = "No title"
                if content.title and isinstance(content.title, str):
                    title_preview = content.title[:50]
                logger.info(
                    "Summarizing content %s: type=%s, title=%s, url=%s, status=%s",
                    content_id,
                    content.content_type,
                    title_preview,
                    content.url,
                    content.status,
                )

                def _persist_failure(reason: str) -> None:
                    metadata = dict(content.content_metadata or {})
                    metadata.pop("summary", None)
                    existing_errors = metadata.get("processing_errors")
                    processing_errors = (
                        existing_errors.copy() if isinstance(existing_errors, list) else []
                    )
                    processing_errors.append(
                        {
                            "stage": "summarization",
                            "reason": reason,
                            "timestamp": datetime.now(UTC).isoformat(),
                        }
                    )
                    metadata["processing_errors"] = processing_errors

                    content.content_metadata = metadata
                    content.status = ContentStatus.FAILED.value
                    content.error_message = reason[:500]
                    content.processed_at = datetime.utcnow()
                    db.commit()

                # Get content to summarize
                metadata = content.content_metadata or {}
                if content.content_type == "article":
                    text_to_summarize = metadata.get("content", "")
                elif content.content_type == "news":
                    text_to_summarize = metadata.get("content", "")
                    # Build aggregator context for news items
                    aggregator_context = self._build_news_context(metadata)
                    if aggregator_context and text_to_summarize:
                        text_to_summarize = (
                            f"Context:\n{aggregator_context}\n\n"
                            f"Article Content:\n{text_to_summarize}"
                        )
                elif content.content_type == "podcast":
                    text_to_summarize = metadata.get("transcript", "")
                else:
                    reason = f"Unknown content type for summarization: {content.content_type}"
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: %s. Content %s, URL: %s",
                        reason,
                        content_id,
                        content.url,
                    )
                    log_processing_error(
                        "summarization",
                        item_id=content_id,
                        error=ValueError(reason),
                        operation="summarize_task",
                        context={
                            "content_type": content.content_type,
                            "url": str(content.url),
                            "title": content.title,
                        },
                    )
                    _persist_failure(reason)
                    return False

                if not text_to_summarize:
                    # Determine what field was expected
                    expected_field = (
                        "transcript" if content.content_type == "podcast" else "content"
                    )
                    reason = f"No text to summarize for content {content_id}"
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: %s. Type: %s, expected field: %s, "
                        "metadata keys: %s, URL: %s",
                        reason,
                        content.content_type,
                        expected_field,
                        list(metadata.keys()),
                        content.url,
                    )
                    log_processing_error(
                        "summarization",
                        item_id=content_id,
                        error=ValueError(reason),
                        operation="summarize_task",
                        context={
                            "content_type": content.content_type,
                            "expected_field": expected_field,
                            "metadata_keys": list(metadata.keys()),
                            "url": str(content.url),
                            "title": content.title,
                        },
                    )
                    _persist_failure(reason)
                    return False

                # Log text length for monitoring
                logger.debug(
                    "Content %s has %d characters to summarize",
                    content_id,
                    len(text_to_summarize),
                )

                # Determine summarization parameters based on content type
                summarization_type = content.content_type
                provider_override = None
                max_bullet_points = 6
                max_quotes = 8

                if content.content_type == "news":
                    summarization_type = "news_digest"
                    provider_override = "openai"
                    max_bullet_points = 4
                    max_quotes = 0

                logger.info(
                    "Calling LLM for content %s: provider=%s, type=%s, "
                    "text_length=%d, max_bullets=%d",
                    content_id,
                    provider_override or "default",
                    summarization_type,
                    len(text_to_summarize),
                    max_bullet_points,
                )

                try:
                    summary = self.llm_service.summarize_content(
                        text_to_summarize,
                        content_type=summarization_type,
                        content_id=content.id,
                        max_bullet_points=max_bullet_points,
                        max_quotes=max_quotes,
                        provider_override=provider_override,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.error(
                        "SUMMARIZE_TASK_ERROR: LLM call failed for content %s (%s). "
                        "Error: %s, URL: %s, text_length: %d",
                        content_id,
                        content.content_type,
                        str(e),
                        content.url,
                        len(text_to_summarize),
                        exc_info=True,
                    )
                    log_processing_error(
                        "summarization",
                        item_id=content_id,
                        error=e,
                        operation="llm_summarization",
                        context={
                            "content_type": content.content_type,
                            "summarization_type": summarization_type,
                            "provider": provider_override or "default",
                            "text_length": len(text_to_summarize),
                            "url": str(content.url),
                            "title": content.title,
                        },
                    )
                    _persist_failure(f"Summarization error: {e}")
                    return False

                if summary is not None:
                    # Update content with summary
                    # Create a new dictionary to ensure SQLAlchemy detects the change
                    metadata = dict(content.content_metadata or {})
                    summary_dict = (
                        summary.model_dump(mode="json", by_alias=True)
                        if hasattr(summary, "model_dump")
                        else summary
                    )

                    # Handle NewsSummary specially to update article metadata
                    if isinstance(summary, NewsSummary):
                        summary_dict.setdefault("classification", summary.classification)
                        metadata["summary"] = summary_dict

                        # Update article section
                        article_section = metadata.get("article", {})
                        article_section.setdefault(
                            "url",
                            summary_dict.get("final_url_after_redirects")
                            or summary_dict.get("article", {}).get("url"),
                        )
                        if summary.title and not article_section.get("title"):
                            article_section["title"] = summary.title
                        metadata["article"] = article_section

                        # Update content title
                        if summary.title:
                            content.title = summary.title

                        logger.info("Generated news digest summary for content %s", content_id)
                    else:
                        metadata["summary"] = summary_dict
                        # Update title if provided
                        if summary_dict.get("title") and not content.title:
                            content.title = summary_dict["title"]
                        logger.info("Generated summary for content %s", content_id)

                    metadata["summarization_date"] = datetime.utcnow().isoformat()

                    # Assign new dictionary to trigger SQLAlchemy change detection
                    content.content_metadata = metadata
                    content.status = ContentStatus.COMPLETED.value
                    content.processed_at = datetime.utcnow()
                    db.commit()

                    return True

                reason = "LLM summarization returned None"
                logger.error(
                    "MISSING_SUMMARY: Content %s (%s) - %s. Title: %s, Text length: %s, URL: %s",
                    content_id,
                    content.content_type,
                    reason,
                    content.title,
                    len(text_to_summarize) if text_to_summarize else 0,
                    content.url,
                )
                log_processing_error(
                    "summarization",
                    item_id=content_id,
                    error=ValueError(reason),
                    operation="llm_summarization",
                    context={
                        "content_type": content.content_type,
                        "summarization_type": summarization_type,
                        "provider": provider_override or "default",
                        "text_length": len(text_to_summarize) if text_to_summarize else 0,
                        "url": str(content.url),
                        "title": content.title,
                    },
                )
                _persist_failure(reason)
                return False

        except Exception as e:
            logger.error(f"Summarization error: {e}", exc_info=True)
            return False

    def _build_news_context(self, metadata: dict[str, Any]) -> str:
        """Build aggregator context string for news items."""
        article = metadata.get("article", {})
        aggregator = metadata.get("aggregator", {})
        lines: list[str] = []

        article_title = article.get("title") or ""
        article_url = article.get("url") or ""

        if article_title:
            lines.append(f"Article Title: {article_title}")
        if article_url:
            lines.append(f"Article URL: {article_url}")

        if aggregator:
            name = aggregator.get("name") or metadata.get("platform")
            agg_title = aggregator.get("title")
            agg_url = aggregator.get("url")
            author = aggregator.get("author")

            context_bits = []
            if name:
                context_bits.append(name)
            if author:
                context_bits.append(f"by {author}")
            if agg_title and agg_title != article_title:
                lines.append(f"Aggregator Headline: {agg_title}")
            if context_bits:
                lines.append("Aggregator Context: " + ", ".join(context_bits))
            if agg_url:
                lines.append(f"Aggregator URL: {agg_url}")

            extra = aggregator.get("metadata") or {}
            highlights = []
            for field in ["score", "comments_count", "likes", "retweets", "replies"]:
                value = extra.get(field)
                if value is not None:
                    highlights.append(f"{field}={value}")
            if highlights:
                lines.append("Signals: " + ", ".join(highlights))

        summary_payload = metadata.get("summary") if isinstance(metadata, dict) else {}
        excerpt = metadata.get("excerpt")
        if not excerpt and isinstance(summary_payload, dict):
            excerpt = summary_payload.get("overview") or summary_payload.get("summary")
        if excerpt:
            lines.append(f"Aggregator Summary: {excerpt}")

        return "\n".join(lines)

    def run(self, max_tasks: int | None = None):
        """
        Run the task processor.

        Args:
            max_tasks: Maximum number of tasks to process. None for unlimited.
        """
        logger.debug(f"Entering run method with max_tasks={max_tasks}")
        # Logging is already set up by the main script
        logger.info(f"Starting sequential task processor (worker_id: {self.worker_id})")

        # Set up signal handlers
        self._shutdown_requested = False

        def signal_handler(signum, frame):
            if not self._shutdown_requested:
                logger.info("\n🛑 Received shutdown signal (Ctrl+C) - stopping gracefully...")
                self._shutdown_requested = True
                self.running = False
            else:
                logger.warning("\n⚠️  Force shutdown requested - exiting immediately")
                sys.exit(1)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        processed_count = 0
        consecutive_empty_polls = 0
        max_empty_polls = 5  # Number of empty polls before backing off
        startup_polls = 0  # Track polls during startup phase
        startup_phase_polls = 10  # Number of aggressive polls on startup

        logger.info(
            f"Entering startup phase with {startup_phase_polls} aggressive polls (100ms intervals)"
        )

        logger.debug(f"About to enter main loop, self.running={self.running}")
        while self.running:
            try:
                # Get next task from queue
                logger.debug(f"Attempting to dequeue task (poll #{startup_polls + 1})")
                task_data = self.queue_service.dequeue(worker_id=self.worker_id)
                logger.debug(f"Dequeue result: {task_data is not None}")

                if not task_data:
                    consecutive_empty_polls += 1
                    startup_polls += 1

                    # During startup phase, poll more aggressively
                    if startup_polls <= startup_phase_polls:
                        logger.debug(
                            f"Startup phase: quick poll {startup_polls}/{startup_phase_polls}"
                        )
                        # Check for shutdown more frequently
                        for _ in range(10):  # 10 x 10ms = 100ms total
                            if not self.running:
                                break
                            time.sleep(0.01)
                    elif consecutive_empty_polls >= max_empty_polls:
                        # Back off when queue is consistently empty
                        logger.debug("Queue empty, backing off...")
                        # Check for shutdown every 100ms during long waits
                        for _ in range(50):  # 50 x 100ms = 5s total
                            if not self.running:
                                break
                            time.sleep(0.1)
                    else:
                        # Check for shutdown every 100ms
                        for _ in range(10):  # 10 x 100ms = 1s total
                            if not self.running:
                                break
                            time.sleep(0.1)
                    continue

                # Reset empty poll counter
                consecutive_empty_polls = 0

                # Mark end of startup phase on first task
                if startup_polls > 0 and startup_polls <= startup_phase_polls:
                    logger.info("Exiting startup phase - found first task")

                logger.info(f"Processing task {task_data['id']} (type: {task_data['task_type']})")

                task_id = task_data["id"]
                retry_count = task_data["retry_count"]

                # Process the task
                success = self.process_task(task_data)

                # Update task status
                self.queue_service.complete_task(task_id, success=success)

                if success:
                    processed_count += 1
                    logger.info(
                        f"Successfully completed task {task_id} "
                        f"(total processed: {processed_count})"
                    )
                else:
                    # Retry logic
                    max_retries = getattr(self.settings, "max_retries", 3)
                    if retry_count < max_retries:
                        delay_seconds = min(60 * (2**retry_count), 3600)
                        self.queue_service.retry_task(task_id, delay_seconds=delay_seconds)
                        logger.info(
                            f"Task {task_id} scheduled for retry "
                            f"{retry_count + 1}/{max_retries} in {delay_seconds}s"
                        )
                    else:
                        logger.error(f"Task {task_id} exceeded max retries ({max_retries})")

                # Check if we've hit max tasks
                if max_tasks and processed_count >= max_tasks:
                    logger.info(f"Reached max tasks limit ({max_tasks}), stopping")
                    break

            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(5)  # Wait before retrying

        logger.info(f"Processor shutting down (processed {processed_count} tasks)")

    def run_single_task(self, task_data: dict[str, Any]) -> bool:
        """
        Process a single task without the main loop.
        Useful for testing or one-off processing.
        """
        setup_logging()
        logger.info(f"Processing single task: {task_data.get('id', 'unknown')}")

        success = self.process_task(task_data)

        # Handle completion and retry logic
        task_id = task_data["id"]
        self.queue_service.complete_task(task_id, success=success)

        if not success and task_data.get("retry_count", 0) < getattr(
            self.settings, "max_retries", 3
        ):
            retry_count = task_data.get("retry_count", 0)
            delay_seconds = min(60 * (2**retry_count), 3600)
            self.queue_service.retry_task(task_id, delay_seconds=delay_seconds)
            logger.info(f"Task {task_id} scheduled for retry")

        return success


if __name__ == "__main__":
    processor = SequentialTaskProcessor()

    # Check for max tasks argument
    max_tasks = None
    if len(sys.argv) > 1:
        try:
            max_tasks = int(sys.argv[1])
        except ValueError:
            logger.error(f"Invalid max_tasks argument: {sys.argv[1]}")
            sys.exit(1)

    processor.run(max_tasks=max_tasks)
