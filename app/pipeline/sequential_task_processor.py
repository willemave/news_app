"""Sequential task processor for robust, simple task processing."""

import signal
import sys
import time
from datetime import datetime
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.core.settings import get_settings
from app.models.schema import Content
from app.pipeline.podcast_workers import PodcastDownloadWorker, PodcastTranscribeWorker
from app.pipeline.worker import ContentWorker
from app.scraping.runner import ScraperRunner
from app.services.anthropic_llm import get_anthropic_summarization_service
from app.services.openai_llm import get_openai_summarization_service
from app.services.queue import QueueService, TaskType

logger = get_logger(__name__)


class SequentialTaskProcessor:
    """Sequential task processor - processes tasks one at a time."""

    def __init__(self):
        logger.debug("Initializing SequentialTaskProcessor...")
        self.queue_service = QueueService()
        logger.debug("QueueService initialized")
        self.anthropic_service = get_anthropic_summarization_service()
        logger.debug("Anthropic summarization service initialized")
        self.openai_service = get_openai_summarization_service()
        logger.debug("OpenAI summarization service initialized")
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
                logger.error("No content_id provided for summarize task")
                return False

            logger.info(f"Processing summarize task for content {content_id}")

            # Get content from database
            with get_db() as db:
                content = db.query(Content).filter(Content.id == content_id).first()
                if not content:
                    logger.error(f"Content {content_id} not found")
                    return False

                # Get content to summarize
                if content.content_type == "article":
                    text_to_summarize = (
                        content.content_metadata.get("content", "")
                        if content.content_metadata
                        else ""
                    )
                elif content.content_type == "podcast":
                    text_to_summarize = (
                        content.content_metadata.get("transcript", "")
                        if content.content_metadata
                        else ""
                    )
                else:
                    logger.error(f"Unknown content type for summarization: {content.content_type}")
                    return False

                if not text_to_summarize:
                    logger.error(f"No text to summarize for content {content_id}")
                    return False

                # Route to appropriate LLM service based on content type
                if content.content_type == "news":
                    llm_service = self.openai_service
                    llm_provider = "openai"
                else:
                    # Articles and Podcasts use Anthropic
                    llm_service = self.anthropic_service
                    llm_provider = "anthropic"

                logger.debug(
                    f"Summarizing content {content_id} using {llm_provider} "
                    f"(type: {content.content_type})"
                )

                # Use LLM to generate summary synchronously
                summary = llm_service.summarize_content(
                    text_to_summarize, content_type=content.content_type
                )

                if summary:
                    # Update content with summary
                    # Create a new dictionary to ensure SQLAlchemy detects the change
                    metadata = dict(content.content_metadata or {})
                    if hasattr(summary, "model_dump"):
                        metadata["summary"] = summary.model_dump(mode="json")
                    else:
                        metadata["summary"] = summary
                    metadata["summarization_date"] = datetime.utcnow().isoformat()

                    # Assign new dictionary to trigger SQLAlchemy change detection
                    content.content_metadata = metadata
                    content.status = "completed"
                    content.processed_at = datetime.utcnow()
                    db.commit()

                    logger.info(f"Successfully summarized content {content_id}")
                    return True
                else:
                    logger.error(f"Failed to generate summary for content {content_id}")
                    return False

        except Exception as e:
            logger.error(f"Summarization error: {e}", exc_info=True)
            return False

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
