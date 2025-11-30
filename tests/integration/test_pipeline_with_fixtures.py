"""Integration tests using real data fixtures.

These tests demonstrate using the content_samples fixtures with the processing
pipeline, showing how real data flows through the system.
"""
from datetime import datetime
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from app.core.db import get_db
from app.models.metadata import ContentStatus, ContentType, StructuredSummary, SummaryBulletPoint, ContentQuote
from app.models.schema import Content
from app.pipeline.worker import ContentWorker
from app.services.queue import QueueService, TaskType


@pytest.fixture
def db_session():
    """Create a database session for testing."""
    with get_db() as db:
        # Clear existing test data
        db.query(Content).filter(Content.id.in_([1, 25, 118, 998, 999])).delete()
        db.commit()
        yield db
        # Cleanup
        db.query(Content).filter(Content.id.in_([1, 25, 118, 998, 999])).delete()
        db.commit()


def create_content_in_db(db, fixture_data: Dict[str, Any]) -> Content:
    """Create content from fixture in the database."""
    from app.tests.conftest import create_content_from_fixture

    content = create_content_from_fixture(fixture_data)
    db.add(content)
    db.commit()
    db.refresh(content)
    return content


class TestPipelineWithRealData:
    """Test processing pipeline with real data examples."""

    @pytest.mark.integration
    def test_process_article_with_real_structure(
        self, db_session, sample_unprocessed_article
    ):
        """Test processing an article using real content structure from fixtures."""
        # Create content from fixture
        content = create_content_in_db(db_session, sample_unprocessed_article)
        assert content.status == ContentStatus.NEW.value

        # Mock external dependencies
        with (
            patch("app.pipeline.worker.get_http_service") as mock_http,
            patch("app.pipeline.worker.get_llm_service") as mock_llm,
            patch("app.pipeline.worker.get_strategy_registry") as mock_registry,
            patch("app.pipeline.worker.get_checkout_manager") as mock_checkout,
            patch("app.pipeline.worker.get_queue_service") as mock_queue,
            patch("app.pipeline.worker.create_error_logger") as mock_error_logger,
        ):
            # Setup strategy mock
            mock_strategy = Mock()
            mock_strategy.preprocess_url.return_value = content.url
            mock_strategy.download_content.return_value = (
                sample_unprocessed_article["content_metadata"]["content"]
            )
            mock_strategy.extract_data.return_value = {
                "title": sample_unprocessed_article["title"],
                "text_content": sample_unprocessed_article["content_metadata"]["content"],
                "content_type": "html",
                "final_url_after_redirects": content.url,
            }
            mock_strategy.prepare_for_llm.return_value = {
                "content_to_summarize": sample_unprocessed_article["content_metadata"]["content"]
            }
            mock_strategy.extract_internal_urls.return_value = []

            mock_registry_instance = Mock()
            mock_registry_instance.get_strategy.return_value = mock_strategy
            mock_registry.return_value = mock_registry_instance

            # Mock LLM to return a realistic summary
            structured_summary = StructuredSummary(
                title="Test Article Summary",
                overview="This is a comprehensive overview of the test article content.",
                bullet_points=[
                    SummaryBulletPoint(
                        text="Software development requires systematic approaches",
                        category="key_finding"
                    ),
                    SummaryBulletPoint(
                        text="Testing and deployment are crucial for reliability",
                        category="methodology"
                    ),
                ],
                quotes=[
                    ContentQuote(
                        text="Write clean, maintainable code",
                        context="Best practices section"
                    )
                ],
                topics=["software engineering", "testing", "deployment"],
                classification="to_read",
            )

            mock_llm_service = Mock()
            mock_llm_service.summarize_content.return_value = structured_summary
            mock_llm.return_value = mock_llm_service

            # Process the content
            worker = ContentWorker()
            result = worker.process_content(content.id, "test-worker")

            assert result is True

            # Verify content was updated
            db_session.refresh(content)
            assert content.status == ContentStatus.COMPLETED.value
            assert "summary" in content.content_metadata
            assert content.content_metadata["summary"]["title"] == "Test Article Summary"
            assert len(content.content_metadata["summary"]["bullet_points"]) == 2

    @pytest.mark.integration
    def test_process_podcast_with_real_structure(
        self, db_session, sample_unprocessed_podcast
    ):
        """Test processing a podcast using real transcript structure."""
        # Create content from fixture
        content = create_content_in_db(db_session, sample_unprocessed_podcast)
        assert content.status == ContentStatus.TRANSCRIBED.value
        assert "transcript" in content.content_metadata

        # Mock dependencies
        with (
            patch("app.pipeline.worker.get_llm_service") as mock_llm,
            patch("app.pipeline.worker.get_checkout_manager") as mock_checkout,
            patch("app.pipeline.worker.get_queue_service") as mock_queue,
            patch("app.pipeline.worker.create_error_logger") as mock_error_logger,
            patch("app.pipeline.worker.PodcastDownloadWorker") as mock_download,
            patch("app.pipeline.worker.PodcastTranscribeWorker") as mock_transcribe,
        ):
            # Mock LLM to return a podcast summary
            structured_summary = StructuredSummary(
                title="Test Podcast: Software Testing Insights",
                overview="Discussion of software testing best practices including unit, integration, and end-to-end testing strategies.",
                bullet_points=[
                    SummaryBulletPoint(
                        text="Comprehensive test suites provide confidence in code quality",
                        category="key_finding"
                    ),
                    SummaryBulletPoint(
                        text="Balance between test coverage and maintenance is crucial",
                        category="methodology"
                    ),
                ],
                quotes=[
                    ContentQuote(
                        text="Tests give you confidence that your code works as expected",
                        context="Speaker discussing testing benefits"
                    )
                ],
                topics=["software testing", "quality assurance", "development"],
                classification="to_read",
            )

            mock_llm_service = Mock()
            mock_llm_service.summarize_content.return_value = structured_summary
            mock_llm.return_value = mock_llm_service

            # Process the content
            worker = ContentWorker()
            result = worker.process_content(content.id, "test-worker")

            # For podcasts with transcript, we should summarize it
            db_session.refresh(content)

            # Verify the LLM was called with the transcript
            mock_llm_service.summarize_content.assert_called_once()
            call_args = mock_llm_service.summarize_content.call_args
            assert "podcast" in call_args.kwargs.get("content_type", "")

    @pytest.mark.integration
    def test_completed_article_structure_matches_fixture(
        self, db_session, sample_article_long
    ):
        """Verify that completed articles in DB match the structure of our fixtures."""
        # Create a completed article from fixture
        content = create_content_in_db(db_session, sample_article_long)

        # Verify it has all expected fields
        assert content.status == ContentStatus.COMPLETED.value
        assert content.content_metadata is not None

        # Verify summary structure
        summary = content.content_metadata.get("summary")
        assert summary is not None
        assert "title" in summary
        assert "overview" in summary
        assert "bullet_points" in summary
        assert isinstance(summary["bullet_points"], list)

        # Verify bullet points structure
        for bp in summary["bullet_points"]:
            assert "text" in bp
            assert "category" in bp

        # Verify quotes structure
        if "quotes" in summary:
            for quote in summary["quotes"]:
                assert "text" in quote
                assert "context" in quote

        # Verify topics
        assert "topics" in summary
        assert isinstance(summary["topics"], list)

    @pytest.mark.integration
    def test_processing_different_content_types(
        self,
        db_session,
        sample_article_short,
        sample_podcast,
    ):
        """Test that different content types can be processed with their fixtures."""
        # Create both types
        article = create_content_in_db(db_session, sample_article_short)
        podcast = create_content_in_db(db_session, sample_podcast)

        # Verify they're in the database with correct types
        assert article.content_type == ContentType.ARTICLE.value
        assert podcast.content_type == ContentType.PODCAST.value

        # Verify article has HTML content
        assert article.content_metadata.get("content_type") == "html"
        assert "content" in article.content_metadata

        # Verify podcast has audio metadata
        assert "transcript" in podcast.content_metadata
        assert "audio_url" in podcast.content_metadata
        assert "duration_seconds" in podcast.content_metadata

    @pytest.mark.integration
    def test_queue_and_process_with_fixtures(
        self, db_session, sample_unprocessed_article
    ):
        """Test complete flow: create content, queue task, process."""
        # Create content
        content = create_content_in_db(db_session, sample_unprocessed_article)

        # Queue processing task
        queue_service = QueueService()
        task_id = queue_service.enqueue(
            task_type=TaskType.PROCESS_CONTENT,
            content_id=content.id
        )

        assert task_id is not None

        # Dequeue the task
        task = queue_service.dequeue(worker_id="test-worker")
        assert task is not None
        assert task["payload"]["content_id"] == content.id

        # Mark task complete
        queue_service.complete_task(task["id"], success=True)

        # Verify task is completed
        from app.models.schema import ProcessingTask
        completed_task = db_session.query(ProcessingTask).filter_by(id=task["id"]).first()
        assert completed_task.status == "completed"

    @pytest.mark.integration
    def test_article_metadata_preservation(
        self, db_session, sample_article_long
    ):
        """Ensure all metadata fields from fixtures are preserved in DB."""
        content = create_content_in_db(db_session, sample_article_long)

        # Verify metadata was preserved
        metadata = content.content_metadata
        assert metadata.get("source") == sample_article_long["content_metadata"]["source"]
        assert metadata.get("content_type") == sample_article_long["content_metadata"]["content_type"]

        # Verify HackerNews metadata
        if "hn_id" in sample_article_long["content_metadata"]:
            assert metadata.get("hn_id") == sample_article_long["content_metadata"]["hn_id"]
            assert metadata.get("score") == sample_article_long["content_metadata"]["score"]

        # Verify summary was preserved
        assert "summary" in metadata
        fixture_summary = sample_article_long["content_metadata"]["summary"]
        db_summary = metadata["summary"]

        assert db_summary["title"] == fixture_summary["title"]
        assert db_summary["overview"] == fixture_summary["overview"]
        assert len(db_summary["bullet_points"]) == len(fixture_summary["bullet_points"])
