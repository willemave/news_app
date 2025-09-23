"""Tests for ContentWorker."""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from pydantic import HttpUrl

from app.pipeline.worker import ContentWorker
from app.models.metadata import ContentData, ContentStatus, ContentType
from app.services.http import NonRetryableError
from app.services.queue import TaskType


@pytest.fixture
def mock_dependencies():
    """Mock all external dependencies."""
    with (
        patch("app.pipeline.worker.get_checkout_manager") as mock_checkout,
        patch("app.pipeline.worker.get_http_service") as mock_http,
        patch("app.pipeline.worker.get_openai_summarization_service") as mock_llm,
        patch("app.pipeline.worker.get_queue_service") as mock_queue,
        patch("app.pipeline.worker.get_strategy_registry") as mock_registry,
        patch("app.pipeline.worker.PodcastDownloadWorker") as mock_download,
        patch("app.pipeline.worker.PodcastTranscribeWorker") as mock_transcribe,
        patch("app.pipeline.worker.create_error_logger") as mock_error_logger,
        patch("app.pipeline.worker.get_db") as mock_get_db,
    ):
        yield {
            "checkout": mock_checkout,
            "http": mock_http,
            "llm": mock_llm,
            "queue": mock_queue,
            "registry": mock_registry,
            "download": mock_download,
            "transcribe": mock_transcribe,
            "error_logger": mock_error_logger,
            "get_db": mock_get_db,
        }


class TestContentWorker:
    """Test cases for ContentWorker."""

    def test_init(self, mock_dependencies):
        """Test worker initialization."""
        worker = ContentWorker()

        assert worker.checkout_manager is not None
        assert worker.http_service is not None
        assert worker.llm_service is not None
        assert worker.queue_service is not None
        assert worker.strategy_registry is not None
        assert worker.podcast_download_worker is not None
        assert worker.podcast_transcribe_worker is not None
        assert worker.error_logger is not None

    def test_process_content_not_found(self, mock_dependencies):
        """Test processing when content not found."""
        worker = ContentWorker()

        # Mock database to return no content
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        result = worker.process_content(123, "test-worker")

        assert result is False

    def test_process_article_sync_success(self, mock_dependencies):
        """Test successful article processing."""
        worker = ContentWorker()

        # Create mock content
        mock_content = Mock()
        mock_content.id = 123
        mock_content.url = "https://example.com/article"
        mock_content.content_type = ContentType.ARTICLE.value
        mock_content.metadata = {}

        # Convert to domain model
        content_data = ContentData(
            id=123,
            url="https://example.com/article",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.NEW,
            metadata={},
            title="Test Article",
            source_feed="test",
            created_at=datetime.utcnow(),
            processed_at=None,
            retry_count=0,
        )

        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        # Mock strategy
        mock_strategy = Mock()
        mock_strategy.preprocess_url.return_value = "https://example.com/article"
        mock_strategy.extract_data.return_value = {
            "title": "Test Article",
            "text_content": "This is test content.",
            "author": "Test Author",
            "publication_date": None,
            "content_type": "html",
            "final_url_after_redirects": "https://example.com/article",
        }
        mock_strategy.prepare_for_llm.return_value = {
            "content_to_summarize": "This is test content."
        }
        mock_strategy.extract_internal_urls.return_value = []

        worker.strategy_registry.get_strategy.return_value = mock_strategy

        # Mock HTTP service
        worker.http_service.fetch_content.return_value = ("<html>content</html>", {})

        # Mock LLM service
        mock_summary = Mock()
        mock_summary.model_dump.return_value = {"summary": "Test summary"}
        worker.llm_service.summarize_content.return_value = mock_summary

        # Mock content_to_domain function
        with patch("app.pipeline.worker.content_to_domain") as mock_converter:
            mock_converter.return_value = content_data

            result = worker.process_content(123, "test-worker")

        assert result is True
        worker.http_service.fetch_content.assert_called_once_with("https://example.com/article")
        mock_strategy.extract_data.assert_called_once()
        worker.llm_service.summarize_content.assert_called_once_with("This is test content.")
        mock_db.commit.assert_called()

    def test_process_article_sync_no_strategy(self, mock_dependencies):
        """Test article processing when no strategy available."""
        worker = ContentWorker()

        # Create mock content
        mock_content = Mock()
        mock_content.id = 123
        mock_content.url = "https://example.com/article"
        mock_content.content_type = ContentType.ARTICLE.value

        content_data = ContentData(
            id=123,
            url="https://example.com/article",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.NEW,
            metadata={},
            title="Test Article",
            source_feed="test",
            created_at=datetime.utcnow(),
            processed_at=None,
            retry_count=0,
        )

        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        # No strategy available
        worker.strategy_registry.get_strategy.return_value = None

        with patch("app.pipeline.worker.content_to_domain") as mock_converter:
            mock_converter.return_value = content_data

            result = worker.process_content(123, "test-worker")

        assert result is False

    def test_process_article_sync_non_retryable_error(self, mock_dependencies):
        """Test article processing with non-retryable error."""
        worker = ContentWorker()

        # Create mock content
        mock_content = Mock()
        mock_content.id = 123
        mock_content.url = "https://example.com/article"
        mock_content.content_type = ContentType.ARTICLE.value
        mock_content.content_metadata = {}

        content_data = ContentData(
            id=123,
            url="https://example.com/article",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.NEW,
            metadata={},
            title="Test Article",
            source_feed="test",
            created_at=datetime.utcnow(),
            processed_at=None,
            retry_count=0,
        )

        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        # Mock strategy
        mock_strategy = Mock()
        mock_strategy.preprocess_url.return_value = "https://example.com/article"
        worker.strategy_registry.get_strategy.return_value = mock_strategy

        # Mock HTTP service to raise NonRetryableError
        worker.http_service.fetch_content.side_effect = NonRetryableError(
            "Non-retryable HTTP 403: Forbidden"
        )

        with patch("app.pipeline.worker.content_to_domain") as mock_converter:
            mock_converter.return_value = content_data

            result = worker.process_content(123, "test-worker")

        assert result is False

    def test_process_news_aggregate(self, mock_dependencies):
        """Test processing of aggregate news content."""
        worker = ContentWorker()

        news_metadata = {
            "platform": "twitter",
            "source": "twitter.com",
            "items": [
                {
                    "title": "Tweet summary",
                    "url": "https://twitter.com/example/status/1",
                    "summary": "Important update",
                    "metadata": {"likes": 10},
                }
            ],
        }

        content_data = ContentData(
            id=999,
            url=HttpUrl("https://example.com/news"),
            content_type=ContentType.NEWS,
            status=ContentStatus.NEW,
            metadata=news_metadata,
            title="Twitter List",
            created_at=datetime.utcnow(),
            is_aggregate=True,
        )

        assert worker._process_news(content_data) is True
        assert content_data.status == ContentStatus.COMPLETED
        assert content_data.processed_at is not None
        assert content_data.metadata.get("rendered_markdown")
        assert content_data.metadata.get("items")[0]["url"] == "https://twitter.com/example/status/1"
        assert mock_content.status == ContentStatus.FAILED.value
        mock_db.commit.assert_called()

    def test_process_article_sync_extraction_error(self, mock_dependencies):
        """Test article processing with extraction error."""
        worker = ContentWorker()

        # Create mock content
        mock_content = Mock()
        mock_content.id = 123
        mock_content.url = "https://example.com/article"
        mock_content.content_type = ContentType.ARTICLE.value

        content_data = ContentData(
            id=123,
            url="https://example.com/article",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.NEW,
            metadata={},
            title="Test Article",
            source_feed="test",
            created_at=datetime.utcnow(),
            processed_at=None,
            retry_count=0,
        )

        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        # Mock strategy
        mock_strategy = Mock()
        mock_strategy.preprocess_url.return_value = "https://example.com/article"
        mock_strategy.extract_data.side_effect = Exception("Extraction failed")
        worker.strategy_registry.get_strategy.return_value = mock_strategy

        # Mock HTTP service
        worker.http_service.fetch_content.return_value = ("<html>content</html>", {})

        with patch("app.pipeline.worker.content_to_domain") as mock_converter:
            mock_converter.return_value = content_data

            result = worker.process_content(123, "test-worker")

        assert result is False
        worker.error_logger.log_processing_error.assert_called()

    def test_process_article_marks_failed_on_crawl_fallback(self, mock_dependencies):
        """Ensure crawl fallback metadata marks the item as failed instead of completed."""
        worker = ContentWorker()
        worker.llm_service = MagicMock()

        mock_content = Mock()
        mock_content.id = 1472
        mock_content.url = (
            "https://signalsandthreads.com/why-ml-needs-a-new-programming-language"
        )
        mock_content.content_type = ContentType.ARTICLE.value

        content_data = ContentData(
            id=1472,
            url="https://signalsandthreads.com/why-ml-needs-a-new-programming-language",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.NEW,
            metadata={},
            title="Why ML Needs a New Programming Language",
            created_at=datetime.utcnow(),
        )

        mock_db = Mock()
        filter_result = mock_db.query.return_value.filter.return_value
        filter_result.first.side_effect = [mock_content, mock_content]
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        fallback_error = "Crawl4ai extraction failed (Unknown error)"

        mock_strategy = Mock()
        mock_strategy.preprocess_url.return_value = (
            "https://signalsandthreads.com/why-ml-needs-a-new-programming-language"
        )
        mock_strategy.extract_data.return_value = {
            "title": "Content from https://signalsandthreads.com/why-ml-needs-a-new-programming-language",
            "text_content": (
                "Failed to extract content from https://signalsandthreads.com/why-ml-needs-a-new-"
                "programming-language. Error: Crawl4ai extraction failed (Unknown error)"
            ),
            "content_type": "html",
            "source": "signalsandthreads.com",
            "final_url_after_redirects": (
                "https://signalsandthreads.com/why-ml-needs-a-new-programming-language"
            ),
            "extraction_error": fallback_error,
        }
        mock_strategy.prepare_for_llm.return_value = {
            "content_to_summarize": (
                "Failed to extract content from https://signalsandthreads.com/why-ml-needs-a-new-"
                "programming-language. Error: Crawl4ai extraction failed (Unknown error)"
            )
        }
        mock_strategy.extract_internal_urls.return_value = []
        worker.strategy_registry.get_strategy.return_value = mock_strategy

        with (
            patch("app.pipeline.worker.content_to_domain") as mock_converter,
            patch("app.pipeline.worker.domain_to_content") as mock_domain_to_content,
        ):
            mock_converter.return_value = content_data

            result = worker.process_content(1472, "test-worker")

        assert result is True
        assert content_data.status == ContentStatus.FAILED
        assert content_data.error_message == fallback_error
        assert content_data.metadata.get("extraction_failed") is True
        assert "summary" not in content_data.metadata
        assert content_data.metadata.get("content") is None
        worker.llm_service.summarize_content.assert_not_called()
        mock_domain_to_content.assert_called_once_with(content_data, mock_content)

    def test_process_podcast_sync_success(self, mock_dependencies):
        """Test successful podcast processing."""
        worker = ContentWorker()

        # Create mock content
        mock_content = Mock()
        mock_content.id = 456
        mock_content.url = "https://example.com/podcast.mp3"
        mock_content.content_type = ContentType.PODCAST.value
        mock_content.metadata = {"audio_url": "https://example.com/podcast.mp3"}

        content_data = ContentData(
            id=456,
            url="https://example.com/podcast.mp3",
            content_type=ContentType.PODCAST,
            status=ContentStatus.NEW,
            metadata={"audio_url": "https://example.com/podcast.mp3"},
            title="Test Podcast",
            source_feed="test",
            created_at=datetime.utcnow(),
            processed_at=None,
            retry_count=0,
        )

        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        # Mock podcast workers
        worker.podcast_download_worker.process_download_task.return_value = True
        worker.podcast_transcribe_worker.process_transcribe_task.return_value = True

        # Mock queue service for task creation
        worker.queue_service.enqueue.side_effect = [1, 2]  # Return task IDs

        with patch("app.pipeline.worker.content_to_domain") as mock_converter:
            mock_converter.return_value = content_data

            result = worker._process_podcast_sync(content_data)

        assert result is True
        # Should have created download task (since file_path is not in metadata)
        assert worker.queue_service.enqueue.call_count == 1
        worker.queue_service.enqueue.assert_called_with(TaskType.DOWNLOAD_AUDIO, content_id=456)

    def test_process_unknown_content_type(self, mock_dependencies):
        """Test processing with unknown content type."""
        worker = ContentWorker()

        # Create mock content with invalid type
        mock_content = Mock()
        mock_content.id = 789
        mock_content.content_type = "UNKNOWN"

        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        with patch("app.pipeline.worker.content_to_domain") as mock_converter:
            # Make content_to_domain raise an error for unknown type
            mock_converter.side_effect = ValueError("Unknown content type")

            result = worker.process_content(789, "test-worker")

        assert result is False
        worker.error_logger.log_processing_error.assert_called()

    async def test_process_content_async(self, mock_dependencies):
        """Test async content processing."""
        worker = ContentWorker()

        # Create mock content
        mock_content = Mock()
        mock_content.id = 123
        mock_content.url = "https://example.com/article"
        mock_content.content_type = ContentType.ARTICLE.value
        mock_content.metadata = {}

        content_data = ContentData(
            id=123,
            url="https://example.com/article",
            content_type=ContentType.ARTICLE,
            status=ContentStatus.NEW,
            metadata={},
            title="Test Article",
            source_feed="test",
            created_at=datetime.utcnow(),
            processed_at=None,
            retry_count=0,
        )

        # Mock database
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_content
        mock_dependencies["get_db"].return_value.__enter__.return_value = mock_db

        # Mock async methods
        worker._process_article = Mock(return_value=True)

        with patch("app.pipeline.worker.content_to_domain") as mock_converter:
            mock_converter.return_value = content_data

            result = await worker.process_content(123, "test-worker")

        assert result is True
        worker._process_article.assert_called_once()
        assert mock_content.status == ContentStatus.COMPLETED.value
        mock_db.commit.assert_called()
