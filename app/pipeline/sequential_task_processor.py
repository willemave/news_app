"""Sequential task processor for robust, simple task processing."""

import signal
import sys
import time

from pydantic import ValidationError

from app.core.logging import get_logger, setup_logging
from app.core.settings import get_settings
from app.pipeline.dispatcher import TaskDispatcher
from app.pipeline.handlers.analyze_url import AnalyzeUrlHandler
from app.pipeline.handlers.dig_deeper import DigDeeperHandler
from app.pipeline.handlers.discover_feeds import DiscoverFeedsHandler
from app.pipeline.handlers.download_audio import DownloadAudioHandler
from app.pipeline.handlers.fetch_discussion import FetchDiscussionHandler
from app.pipeline.handlers.generate_image import GenerateImageHandler
from app.pipeline.handlers.onboarding_discover import OnboardingDiscoverHandler
from app.pipeline.handlers.process_content import ProcessContentHandler
from app.pipeline.handlers.scrape import ScrapeHandler
from app.pipeline.handlers.summarize import SummarizeHandler
from app.pipeline.handlers.transcribe import TranscribeHandler
from app.pipeline.task_context import TaskContext
from app.pipeline.task_handler import TaskHandler
from app.pipeline.task_models import TaskEnvelope, TaskResult
from app.pipeline.worker import get_llm_service
from app.services.queue import QueueService, TaskQueue

logger = get_logger(__name__)


class SequentialTaskProcessor:
    """Sequential task processor - processes tasks one at a time."""

    def __init__(
        self,
        queue_name: TaskQueue | str = TaskQueue.CONTENT,
        worker_slot: int = 1,
    ) -> None:
        logger.debug("Initializing SequentialTaskProcessor...")
        self.queue_service = QueueService()
        logger.debug("QueueService initialized")
        self.llm_service = get_llm_service()
        logger.debug("Shared summarization service initialized")
        self.settings = get_settings()
        logger.debug("Settings loaded")
        self.running = True
        self.queue_name = QueueService._normalize_queue_name(queue_name) or TaskQueue.CONTENT.value
        self.worker_slot = worker_slot
        self.worker_id = f"{self.queue_name}-processor-{self.worker_slot}"
        logger.debug(
            "SequentialTaskProcessor initialized with worker_id: %s queue=%s",
            self.worker_id,
            self.queue_name,
        )
        self.context = TaskContext(
            queue_service=self.queue_service,
            settings=self.settings,
            llm_service=self.llm_service,
            worker_id=self.worker_id,
        )
        self.dispatcher = TaskDispatcher(self._build_handlers())

    def _build_handlers(self) -> list[TaskHandler]:
        """Build task handlers for dispatching."""
        return [
            ScrapeHandler(),
            AnalyzeUrlHandler(),
            ProcessContentHandler(),
            DownloadAudioHandler(),
            TranscribeHandler(),
            SummarizeHandler(),
            FetchDiscussionHandler(),
            GenerateImageHandler(),
            DiscoverFeedsHandler(),
            OnboardingDiscoverHandler(),
            DigDeeperHandler(),
        ]

    def process_task(self, task: TaskEnvelope) -> TaskResult:
        """Process a single task."""
        task_id = task.id
        start_time = time.time()

        try:
            logger.info("Processing task %s of type %s", task_id, task.task_type)
            logger.debug("Task %s data: %s", task_id, task.to_legacy_task_data())
            result = self.dispatcher.dispatch(task, self.context)
            if not result.success and not result.error_message:
                result = TaskResult(
                    success=False,
                    error_message=f"{task.task_type.value} returned False",
                    retry_delay_seconds=result.retry_delay_seconds,
                    retryable=result.retryable,
                )
            elapsed = time.time() - start_time
            logger.info(
                "Task %s completed in %.2fs with result: %s",
                task_id,
                elapsed,
                result.success,
            )
            return result

        except Exception as exc:  # noqa: BLE001
            elapsed = time.time() - start_time
            logger.error(
                "Error processing task %s after %.2fs: %s",
                task_id,
                elapsed,
                exc,
                exc_info=True,
            )
            return TaskResult.fail(str(exc))

    def run(self, max_tasks: int | None = None) -> None:
        """
        Run the task processor.

        Args:
            max_tasks: Maximum number of tasks to process. None for unlimited.
        """
        logger.debug("Entering run method with max_tasks=%s", max_tasks)
        logger.info(
            "Starting sequential task processor (worker_id: %s, queue=%s)",
            self.worker_id,
            self.queue_name,
        )

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
        max_empty_polls = 5
        startup_polls = 0
        startup_phase_polls = 10

        logger.info(
            "Entering startup phase with %s aggressive polls (100ms intervals)",
            startup_phase_polls,
        )

        logger.debug("About to enter main loop, self.running=%s", self.running)
        while self.running:
            try:
                logger.debug("Attempting to dequeue task (poll #%s)", startup_polls + 1)
                task_data = self.queue_service.dequeue(
                    worker_id=self.worker_id,
                    queue_name=self.queue_name,
                )
                logger.debug("Dequeue result: %s", task_data is not None)

                if not task_data:
                    consecutive_empty_polls += 1
                    startup_polls += 1

                    if startup_polls <= startup_phase_polls:
                        logger.debug(
                            "Startup phase: quick poll %s/%s",
                            startup_polls,
                            startup_phase_polls,
                        )
                        for _ in range(10):
                            if not self.running:
                                break
                            time.sleep(0.01)
                    elif consecutive_empty_polls >= max_empty_polls:
                        logger.debug("Queue empty, backing off...")
                        for _ in range(50):
                            if not self.running:
                                break
                            time.sleep(0.1)
                    else:
                        for _ in range(10):
                            if not self.running:
                                break
                            time.sleep(0.1)
                    continue

                consecutive_empty_polls = 0

                if startup_polls > 0 and startup_polls <= startup_phase_polls:
                    logger.info("Exiting startup phase - found first task")

                try:
                    task = TaskEnvelope.from_queue_data(task_data)
                except ValidationError as exc:
                    task_id = task_data.get("id")
                    logger.error(
                        "Invalid task payload for %s: %s",
                        task_id,
                        exc,
                        extra={
                            "component": "sequential_task_processor",
                            "operation": "task_parse",
                            "item_id": task_id,
                            "context_data": {"task_data": task_data},
                        },
                    )
                    if task_id is not None:
                        self.queue_service.complete_task(
                            int(task_id),
                            success=False,
                            error_message="Invalid task payload",
                        )
                    continue
                logger.info("Processing task %s (type: %s)", task.id, task.task_type.value)

                retry_count = task.retry_count

                result = self.process_task(task)

                self.queue_service.complete_task(
                    task.id,
                    success=result.success,
                    error_message=result.error_message,
                )

                if result.success:
                    processed_count += 1
                    logger.info(
                        "Successfully completed task %s (total processed: %s)",
                        task.id,
                        processed_count,
                    )
                else:
                    max_retries = getattr(self.settings, "max_retries", 3)
                    if result.retryable and retry_count < max_retries:
                        delay_seconds = min(60 * (2**retry_count), 3600)
                        self.queue_service.retry_task(task.id, delay_seconds=delay_seconds)
                        logger.info(
                            "Task %s scheduled for retry %s/%s in %ss",
                            task.id,
                            retry_count + 1,
                            max_retries,
                            delay_seconds,
                        )
                    elif not result.retryable:
                        logger.info(
                            "Task %s failed with non-retryable error: %s",
                            task.id,
                            result.error_message or "unknown error",
                        )
                    else:
                        logger.error(
                            "Task %s exceeded max retries (%s)",
                            task.id,
                            max_retries,
                        )

                if max_tasks and processed_count >= max_tasks:
                    logger.info("Reached max tasks limit (%s), stopping", max_tasks)
                    break

            except Exception as exc:  # noqa: BLE001
                logger.error("Error in main loop: %s", exc, exc_info=True)
                time.sleep(5)

        logger.info("Processor shutting down (processed %s tasks)", processed_count)

    def run_single_task(self, task_data: dict[str, object]) -> bool:
        """
        Process a single task without the main loop.
        Useful for testing or one-off processing.
        """
        setup_logging()
        logger.info("Processing single task: %s", task_data.get("id", "unknown"))

        try:
            task = TaskEnvelope.from_queue_data(task_data)
        except ValidationError as exc:
            task_id = task_data.get("id")
            logger.error(
                "Invalid task payload for %s: %s",
                task_id,
                exc,
                extra={
                    "component": "sequential_task_processor",
                    "operation": "task_parse",
                    "item_id": task_id,
                    "context_data": {"task_data": task_data},
                },
            )
            if task_id is not None:
                self.queue_service.complete_task(
                    int(task_id),
                    success=False,
                    error_message="Invalid task payload",
                )
            return False

        result = self.process_task(task)

        task_id = task.id
        self.queue_service.complete_task(
            task_id,
            success=result.success,
            error_message=result.error_message,
        )

        if (
            not result.success
            and result.retryable
            and task.retry_count < getattr(self.settings, "max_retries", 3)
        ):
            retry_count = task.retry_count
            delay_seconds = min(60 * (2**retry_count), 3600)
            self.queue_service.retry_task(task_id, delay_seconds=delay_seconds)
            logger.info("Task %s scheduled for retry", task_id)

        return result.success


if __name__ == "__main__":
    processor = SequentialTaskProcessor()

    max_tasks = None
    if len(sys.argv) > 1:
        try:
            max_tasks = int(sys.argv[1])
        except ValueError:
            logger.error("Invalid max_tasks argument: %s", sys.argv[1])
            sys.exit(1)

    processor.run(max_tasks=max_tasks)
