"""Tests for the sequential task processor."""

from unittest.mock import Mock, patch

import pytest

from app.pipeline.sequential_task_processor import SequentialTaskProcessor
from app.services.queue import TaskType


@pytest.fixture
def processor():
    """Create a processor instance for testing."""
    with (
        patch("app.pipeline.sequential_task_processor.QueueService"),
        patch("app.pipeline.sequential_task_processor.get_llm_service"),
    ):
        processor = SequentialTaskProcessor()
        processor.queue_service = Mock()
        processor.llm_service = Mock()
        return processor


class TestSequentialTaskProcessor:
    """Test cases for SequentialTaskProcessor."""

    def test_init(self, processor):
        """Test processor initialization."""
        assert processor.running is True
        assert processor.worker_id == "sequential-processor"
        assert processor.queue_service is not None
        assert processor.llm_service is not None

    def test_process_task_unknown_type(self, processor):
        """Test processing task with unknown type."""
        task_data = {"id": 1, "task_type": "UNKNOWN_TYPE", "retry_count": 0}

        result = processor.process_task(task_data)
        assert result is False

    def test_process_scrape_task_success(self, processor):
        """Test successful scrape task processing."""
        task_data = {
            "id": 1,
            "task_type": TaskType.SCRAPE.value,
            "retry_count": 0,
            "payload": {"sources": ["hackernews"]},
        }

        with patch("app.pipeline.sequential_task_processor.ScraperRunner") as mock_runner:
            mock_instance = Mock()
            mock_instance.run_scraper.return_value = {"hackernews": 10}
            mock_runner.return_value = mock_instance

            result = processor.process_task(task_data)
            assert result is True
            mock_instance.run_scraper.assert_called_once_with("hackernews")

    def test_process_scrape_task_all_sources(self, processor):
        """Test scrape task with 'all' sources."""
        task_data = {
            "id": 1,
            "task_type": TaskType.SCRAPE.value,
            "retry_count": 0,
            "payload": {"sources": ["all"]},
        }

        with patch("app.pipeline.sequential_task_processor.ScraperRunner") as mock_runner:
            mock_instance = Mock()
            mock_runner.return_value = mock_instance

            result = processor.process_task(task_data)
            assert result is True
            mock_instance.run_all.assert_called_once()

    def test_process_content_task_no_content_id(self, processor):
        """Test content task without content_id."""
        task_data = {
            "id": 1,
            "task_type": TaskType.PROCESS_CONTENT.value,
            "retry_count": 0,
            "payload": {},
        }

        result = processor.process_task(task_data)
        assert result is False

    def test_process_content_task_success(self, processor):
        """Test successful content processing."""
        task_data = {
            "id": 1,
            "task_type": TaskType.PROCESS_CONTENT.value,
            "retry_count": 0,
            "content_id": 123,
        }

        with patch("app.pipeline.sequential_task_processor.ContentWorker") as mock_worker:
            mock_instance = Mock()
            mock_instance.process_content.return_value = True
            mock_worker.return_value = mock_instance

            result = processor.process_task(task_data)
            assert result is True
            mock_instance.process_content.assert_called_once_with(123, "sequential-processor")

    def test_process_download_task_success(self, processor):
        """Test successful download task."""
        task_data = {
            "id": 1,
            "task_type": TaskType.DOWNLOAD_AUDIO.value,
            "retry_count": 0,
            "content_id": 456,
        }

        with patch("app.pipeline.sequential_task_processor.PodcastDownloadWorker") as mock_worker:
            mock_instance = Mock()
            mock_instance.process_download_task.return_value = True
            mock_worker.return_value = mock_instance

            result = processor.process_task(task_data)
            assert result is True
            mock_instance.process_download_task.assert_called_once_with(456)

    def test_process_transcribe_task_success(self, processor):
        """Test successful transcribe task."""
        task_data = {
            "id": 1,
            "task_type": TaskType.TRANSCRIBE.value,
            "retry_count": 0,
            "content_id": 789,
        }

        with patch("app.pipeline.sequential_task_processor.PodcastTranscribeWorker") as mock_worker:
            mock_instance = Mock()
            mock_instance.process_transcribe_task.return_value = True
            mock_worker.return_value = mock_instance

            result = processor.process_task(task_data)
            assert result is True
            mock_instance.process_transcribe_task.assert_called_once_with(789)

    def test_process_summarize_task_success(self, processor):
        """Test successful summarize task processing."""
        task_data = {
            "id": 1,
            "task_type": TaskType.SUMMARIZE.value,
            "retry_count": 0,
            "content_id": 123,
        }

        # Mock database content
        mock_content = Mock()
        mock_content.id = 123
        mock_content.content_type = "article"
        mock_content.metadata = {"content": "This is test content for summarization."}

        # Mock database session
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content

        # Mock LLM service
        mock_summary = Mock()
        mock_summary.model_dump.return_value = {"summary": "Test summary"}
        processor.llm_service.summarize_content.return_value = mock_summary

        with patch("app.pipeline.sequential_task_processor.get_db") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = mock_db

            result = processor.process_task(task_data)

            assert result is True
            processor.llm_service.summarize_content.assert_called_once_with(
                "This is test content for summarization.",
                content_type="article",
                content_id=123,
            )
            assert mock_content.status == "completed"
            assert mock_content.metadata["summary"] == {"summary": "Test summary"}
            mock_db.commit.assert_called_once()

    def test_process_summarize_task_no_content(self, processor):
        """Test summarize task when content not found."""
        task_data = {
            "id": 1,
            "task_type": TaskType.SUMMARIZE.value,
            "retry_count": 0,
            "content_id": 999,
        }

        # Mock database to return no content
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        with patch("app.pipeline.sequential_task_processor.get_db") as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = mock_db

            result = processor.process_task(task_data)
            assert result is False

    def test_run_processes_tasks_sequentially(self, processor):
        """Test that run method processes tasks sequentially."""
        # Mock tasks
        task1 = {"id": 1, "task_type": TaskType.SCRAPE.value, "retry_count": 0, "payload": {}}
        task2 = {
            "id": 2,
            "task_type": TaskType.PROCESS_CONTENT.value,
            "retry_count": 0,
            "content_id": 123,
        }

        # Mock queue to return tasks then None
        processor.queue_service.dequeue.side_effect = [task1, task2, None]
        processor.process_task = Mock(return_value=True)

        # Run with max_tasks to stop after 2
        with patch("app.pipeline.sequential_task_processor.setup_logging"):
            processor.run(max_tasks=2)

        # Verify both tasks were processed
        assert processor.process_task.call_count == 2
        processor.queue_service.complete_task.assert_any_call(1, success=True)
        processor.queue_service.complete_task.assert_any_call(2, success=True)

    def test_run_retry_logic(self, processor):
        """Test retry logic for failed tasks."""
        task_data = {
            "id": 1,
            "task_type": TaskType.DOWNLOAD_AUDIO.value,
            "retry_count": 1,
            "content_id": 789,
        }

        # Mock to return one task then stop
        call_count = 0

        def mock_dequeue(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return task_data
            processor.running = False  # Stop after first task
            return None

        processor.queue_service.dequeue.side_effect = mock_dequeue
        processor.process_task = Mock(return_value=False)  # Task fails
        processor.settings.max_retries = 3

        # Run
        with patch("app.pipeline.sequential_task_processor.setup_logging"):
            processor.run()

        # Verify retry was scheduled
        processor.queue_service.retry_task.assert_called_once()
        call_args = processor.queue_service.retry_task.call_args
        assert call_args[0][0] == 1  # task_id
        assert call_args[1]["delay_seconds"] == 120  # 60 * 2^1

    def test_run_max_retries_exceeded(self, processor):
        """Test behavior when max retries exceeded."""
        task_data = {
            "id": 1,
            "task_type": TaskType.TRANSCRIBE.value,
            "retry_count": 3,
            "content_id": 999,
        }

        # Mock to return one task then stop
        call_count = 0

        def mock_dequeue(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return task_data
            processor.running = False  # Stop after first task
            return None

        processor.queue_service.dequeue.side_effect = mock_dequeue
        processor.process_task = Mock(return_value=False)  # Task fails
        processor.settings.max_retries = 3

        with patch("app.pipeline.sequential_task_processor.setup_logging"):
            processor.run()

        # Verify no retry was scheduled
        processor.queue_service.retry_task.assert_not_called()

    def test_run_empty_queue_backoff(self, processor):
        """Test backoff behavior when queue is empty."""
        # Return None to simulate empty queue for several polls, then stop
        call_count = 0

        def mock_dequeue(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 10:  # Stop after 10 empty polls
                processor.running = False
            return None

        processor.queue_service.dequeue.side_effect = mock_dequeue

        with patch("app.pipeline.sequential_task_processor.setup_logging"):
            with patch("time.sleep") as mock_sleep:
                processor.run()

        # Should have called sleep with backoff after multiple empty polls
        assert mock_sleep.called
        # Should have called with 5 second backoff after max_empty_polls
        mock_sleep.assert_any_call(5)

    def test_run_signal_handler(self, processor):
        """Test signal handler setup."""
        with patch("signal.signal") as mock_signal:
            with patch("app.pipeline.sequential_task_processor.setup_logging"):
                # Stop immediately
                processor.running = False
                processor.run()

                # Verify signal handlers were set
                assert mock_signal.call_count >= 2  # SIGINT and SIGTERM

    def test_run_single_task(self, processor):
        """Test run_single_task method."""
        task_data = {
            "id": 1,
            "task_type": TaskType.PROCESS_CONTENT.value,
            "retry_count": 0,
            "content_id": 123,
        }

        processor.process_task = Mock(return_value=True)

        with patch("app.pipeline.sequential_task_processor.setup_logging"):
            result = processor.run_single_task(task_data)

        assert result is True
        processor.process_task.assert_called_once_with(task_data)
        processor.queue_service.complete_task.assert_called_once_with(1, success=True)

    def test_run_single_task_with_retry(self, processor):
        """Test run_single_task with failed task that should retry."""
        task_data = {
            "id": 1,
            "task_type": TaskType.DOWNLOAD_AUDIO.value,
            "retry_count": 0,
            "content_id": 456,
        }

        processor.process_task = Mock(return_value=False)
        processor.settings.max_retries = 3

        with patch("app.pipeline.sequential_task_processor.setup_logging"):
            result = processor.run_single_task(task_data)

        assert result is False
        processor.queue_service.complete_task.assert_called_once_with(1, success=False)
        processor.queue_service.retry_task.assert_called_once()

    def test_process_task_exception_handling(self, processor):
        """Test exception handling in process_task."""
        task_data = {
            "id": 1,
            "task_type": TaskType.SCRAPE.value,
            "retry_count": 0,
            "payload": {"sources": ["all"]},
        }

        with patch("app.pipeline.sequential_task_processor.ScraperRunner") as mock_runner:
            mock_runner.side_effect = Exception("Test error")

            result = processor.process_task(task_data)
            assert result is False

    def test_run_main_loop_exception_handling(self, processor):
        """Test exception handling in main loop."""
        # Mock dequeue to raise exception then stop
        call_count = 0

        def mock_dequeue_with_error(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 2:
                processor.running = False
                return None
            raise Exception("Queue error")

        processor.queue_service.dequeue.side_effect = mock_dequeue_with_error

        with patch("app.pipeline.sequential_task_processor.setup_logging"):
            with patch("time.sleep"):
                # Should not raise, just log and continue
                processor.run()

        # Processor should have stopped gracefully
        assert processor.running is False
        assert call_count > 2  # Should have tried multiple times
