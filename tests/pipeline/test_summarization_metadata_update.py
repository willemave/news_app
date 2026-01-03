"""Test that summarization properly updates content metadata."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from app.models.metadata import (
    ContentQuote,
    NewsSummary,
    StructuredSummary,
    SummaryBulletPoint,
)
from app.models.schema import Content
from app.pipeline.sequential_task_processor import SequentialTaskProcessor


@pytest.fixture
def db_session():
    """Fixture for mocked database session."""
    with patch("app.pipeline.sequential_task_processor.get_db") as mock_get_db:
        mock_session = MagicMock()
        mock_session.query.return_value = mock_session
        mock_session.filter.return_value = mock_session
        mock_get_db.return_value.__enter__.return_value = mock_session
        yield mock_session


@pytest.fixture
def mock_structured_summary():
    """Create a mock structured summary."""
    return StructuredSummary(
        title="Test Summary Title",
        overview=(
            "This is a test overview of the content that provides detailed "
            "information about the main topics discussed in the material."
        ),
        bullet_points=[
            SummaryBulletPoint(text="First key point about the main topic", category="key_finding"),
            SummaryBulletPoint(
                text="Second key point describing the methodology", category="methodology"
            ),
            SummaryBulletPoint(
                text="Third key point with important conclusions", category="conclusion"
            ),
        ],
        quotes=[ContentQuote(text="This is an important quote", context="Author Name")],
        topics=["Technology", "Innovation"],
        classification="to_read",
        full_markdown="# Test Content\n\nFull markdown content here...",
    )


def test_summarize_task_updates_podcast_metadata(db_session, mock_structured_summary):
    """Test that summarize task properly updates podcast metadata."""
    # Create a test podcast with transcript
    content = Mock(spec=Content)
    content.id = 1
    content.content_type = "podcast"
    content.status = "processing"
    content.content_metadata = {
        "audio_url": "https://example.com/podcast.mp3",
        "transcript": "This is a test transcript of the podcast episode.",
        "source": "Test Podcast Feed",
    }

    # Mock the database query to return our content
    db_session.first.return_value = content

    # Create processor and mock LLM service
    processor = SequentialTaskProcessor()

    with patch.object(processor.llm_service, "summarize_content") as mock_summarize:
        mock_summarize.return_value = mock_structured_summary

        # Process the summarize task
        task_data = {
            "id": 1,
            "task_type": "summarize",
            "content_id": 1,
            "payload": {"content_id": 1},
        }

        result = processor._process_summarize_task(task_data)

        # Verify the task succeeded
        assert result is True

        # Verify metadata was updated with a new dictionary
        # The key assertion: content_metadata should be assigned a new dict
        assert content.content_metadata != {
            "audio_url": "https://example.com/podcast.mp3",
            "transcript": "This is a test transcript of the podcast episode.",
            "source": "Test Podcast Feed",
        }

        # Verify summary was added
        assert "summary" in content.content_metadata
        assert "summarization_date" in content.content_metadata
        expected_summary = mock_structured_summary.model_dump(mode="json")

        # Verify summary content matches structured payload
        summary = content.content_metadata["summary"]
        assert summary == expected_summary

        # Verify original metadata is preserved
        assert content.content_metadata["audio_url"] == "https://example.com/podcast.mp3"
        assert content.content_metadata["transcript"] == (
            "This is a test transcript of the podcast episode."
        )
        assert content.content_metadata["source"] == "Test Podcast Feed"

        # Verify status was updated
        assert content.status == "completed"
        assert content.processed_at is not None


def test_summarize_task_updates_article_metadata(db_session, mock_structured_summary):
    """Test that summarize task properly updates article metadata."""
    # Create a test article with content
    content = Mock(spec=Content)
    content.id = 1
    content.content_type = "article"
    content.status = "processing"
    content.content_metadata = {
        "content": "This is the full text content of the article.",
        "author": "Test Author",
        "source": "Test Blog",
    }

    # Mock the database query to return our content
    db_session.first.return_value = content

    # Create processor and mock LLM service
    processor = SequentialTaskProcessor()

    with patch.object(processor.llm_service, "summarize_content") as mock_summarize:
        mock_summarize.return_value = mock_structured_summary

        # Process the summarize task
        task_data = {
            "id": 1,
            "task_type": "summarize",
            "content_id": 1,
            "payload": {"content_id": 1},
        }

        result = processor._process_summarize_task(task_data)

        # Verify the task succeeded
        assert result is True

        # Verify metadata was updated with summary
        assert "summary" in content.content_metadata
        expected_summary = mock_structured_summary.model_dump(mode="json")
        assert content.content_metadata["summary"] == expected_summary

        # Verify original metadata is preserved
        assert content.content_metadata["author"] == "Test Author"
        assert content.content_metadata["source"] == "Test Blog"


def test_summarize_task_updates_news_metadata(db_session):
    """Test that summarize task properly updates news metadata with aggregator context."""
    # Create a mock news summary (NewsSummary uses string bullet points, not SummaryBulletPoint)
    news_summary = NewsSummary(
        title="Breaking: Tech Company Announces New Product",
        overview="Major tech company revealed their latest innovation today.",
        bullet_points=[
            "New product features AI integration",
            "Expected to ship Q1 2025",
        ],
        classification="to_read",
    )

    # Create test news content with aggregator metadata
    content = Mock(spec=Content)
    content.id = 1
    content.title = None
    content.content_type = "news"
    content.status = "processing"
    content.content_metadata = {
        "content": "Full article text about the new product announcement...",
        "article": {
            "title": "Tech Company Product Launch",
            "url": "https://example.com/article",
        },
        "aggregator": {
            "name": "HackerNews",
            "title": "Show HN: New Product",
            "metadata": {"score": 150, "comments_count": 42},
        },
        "discussion_url": "https://news.ycombinator.com/item?id=12345",
        "platform": "hackernews",
    }

    # Mock the database query to return our content
    db_session.first.return_value = content

    # Create processor and mock LLM service
    processor = SequentialTaskProcessor()

    with patch.object(processor.llm_service, "summarize_content") as mock_summarize:
        mock_summarize.return_value = news_summary

        # Process the summarize task
        task_data = {
            "id": 1,
            "task_type": "summarize",
            "content_id": 1,
            "payload": {"content_id": 1},
        }

        result = processor._process_summarize_task(task_data)

        # Verify the task succeeded
        assert result is True

        # Verify summarize_content was called with news_digest type and openai provider
        mock_summarize.assert_called_once()
        call_kwargs = mock_summarize.call_args.kwargs
        assert call_kwargs["content_type"] == "news_digest"
        assert call_kwargs["provider_override"] == "openai"
        assert call_kwargs["max_bullet_points"] == 4
        assert call_kwargs["max_quotes"] == 0

        # Verify the content passed includes aggregator context
        call_args = mock_summarize.call_args.args
        assert "Context:" in call_args[0]
        assert "Article Title:" in call_args[0]
        assert "Aggregator Context:" in call_args[0]

        # Verify summary was added to metadata
        assert "summary" in content.content_metadata
        assert content.content_metadata["summary"]["classification"] == "to_read"

        # Verify title was updated from NewsSummary
        assert content.title == "Breaking: Tech Company Announces New Product"

        # Verify status was updated
        assert content.status == "completed"


def test_summarize_task_handles_missing_content(db_session):
    """Test that summarize task handles missing content gracefully."""
    # Mock the database query to return None (content not found)
    db_session.first.return_value = None

    processor = SequentialTaskProcessor()

    # Process task for non-existent content
    task_data = {
        "id": 1,
        "task_type": "summarize",
        "content_id": 99999,
        "payload": {"content_id": 99999},
    }

    result = processor._process_summarize_task(task_data)

    # Should return False for missing content
    assert result is False


def test_summarize_task_handles_missing_text(db_session):
    """Test that summarize task handles content without text gracefully."""
    # Create a podcast without transcript
    content = Mock(spec=Content)
    content.id = 1
    content.content_type = "podcast"
    content.status = "processing"
    content.content_metadata = {
        "audio_url": "https://example.com/podcast.mp3"
        # No transcript
    }

    # Mock the database query to return our content
    db_session.first.return_value = content

    processor = SequentialTaskProcessor()

    task_data = {"id": 1, "task_type": "summarize", "content_id": 1, "payload": {"content_id": 1}}

    result = processor._process_summarize_task(task_data)

    # Should return False when no text to summarize
    assert result is False
    assert content.status == "failed"
    assert "No text to summarize" in (content.error_message or "")
    assert isinstance(content.content_metadata, dict)
    assert "processing_errors" in content.content_metadata
    processing_errors = content.content_metadata["processing_errors"]
    assert isinstance(processing_errors, list)
    assert processing_errors
    assert processing_errors[-1]["stage"] == "summarization"
