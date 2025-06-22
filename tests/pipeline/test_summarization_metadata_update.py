"""Test that summarization properly updates content metadata."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from app.models.metadata import ContentQuote, StructuredSummary, SummaryBulletPoint
from app.models.schema import Content
from app.pipeline.sequential_task_processor import SequentialTaskProcessor


@pytest.fixture
def db_session():
    """Fixture for mocked database session."""
    with patch('app.pipeline.sequential_task_processor.get_db') as mock_get_db:
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
        overview=("This is a test overview of the content that provides detailed "
                 "information about the main topics discussed in the material."),
        bullet_points=[
            SummaryBulletPoint(
                text="First key point about the main topic", 
                category="key_finding"
            ),
            SummaryBulletPoint(
                text="Second key point describing the methodology", 
                category="methodology"
            ),
            SummaryBulletPoint(
                text="Third key point with important conclusions", 
                category="conclusion"
            ),
        ],
        quotes=[
            ContentQuote(text="This is an important quote", context="Author Name")
        ],
        topics=["Technology", "Innovation"],
        classification="to_read",
        full_markdown="# Test Content\n\nFull markdown content here..."
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
        "source": "Test Podcast Feed"
    }
    
    # Mock the database query to return our content
    db_session.first.return_value = content
    
    # Create processor and mock LLM service
    processor = SequentialTaskProcessor()
    
    with patch.object(processor.llm_service, 'summarize_content_sync') as mock_summarize:
        mock_summarize.return_value = mock_structured_summary
        
        # Process the summarize task
        task_data = {
            "id": 1,
            "task_type": "summarize",
            "content_id": 1,
            "payload": {"content_id": 1}
        }
        
        result = processor._process_summarize_task(task_data)
        
        # Verify the task succeeded
        assert result is True
        
        # Verify metadata was updated with a new dictionary
        # The key assertion: content_metadata should be assigned a new dict
        assert content.content_metadata != {
            "audio_url": "https://example.com/podcast.mp3",
            "transcript": "This is a test transcript of the podcast episode.",
            "source": "Test Podcast Feed"
        }
        
        # Verify summary was added
        assert "summary" in content.content_metadata
        assert "summarization_date" in content.content_metadata
        
        # Verify summary content
        summary = content.content_metadata["summary"]
        assert summary["title"] == "Test Summary Title"
        assert summary["overview"] == ("This is a test overview of the content that provides "
                                          "detailed information about the main topics discussed "
                                          "in the material.")
        assert len(summary["bullet_points"]) == 3
        assert summary["classification"] == "to_read"
        
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
        "source": "Test Blog"
    }
    
    # Mock the database query to return our content
    db_session.first.return_value = content
    
    # Create processor and mock LLM service
    processor = SequentialTaskProcessor()
    
    with patch.object(processor.llm_service, 'summarize_content_sync') as mock_summarize:
        mock_summarize.return_value = mock_structured_summary
        
        # Process the summarize task
        task_data = {
            "id": 1,
            "task_type": "summarize",
            "content_id": 1,
            "payload": {"content_id": 1}
        }
        
        result = processor._process_summarize_task(task_data)
        
        # Verify the task succeeded
        assert result is True
        
        # Verify metadata was updated with summary
        assert "summary" in content.content_metadata
        assert content.content_metadata["summary"]["title"] == "Test Summary Title"
        
        # Verify original metadata is preserved
        assert content.content_metadata["author"] == "Test Author"
        assert content.content_metadata["source"] == "Test Blog"


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
        "payload": {"content_id": 99999}
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
    
    task_data = {
        "id": 1,
        "task_type": "summarize",
        "content_id": 1,
        "payload": {"content_id": 1}
    }
    
    result = processor._process_summarize_task(task_data)
    
    # Should return False when no text to summarize
    assert result is False