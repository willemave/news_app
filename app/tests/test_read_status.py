"""Tests for content read status functionality."""
from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.models.schema import Content
from app.services import read_status


@pytest.fixture
def sample_content(db_session: Session) -> Content:
    """Create sample content for testing."""
    content = Content(
        content_type="article",
        url="https://example.com/article",
        title="Test Article",
        status="completed",
        content_metadata={"summary": "Test summary"},
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def test_mark_content_as_read(db_session: Session, sample_content: Content):
    """Test marking content as read."""
    # Mark content as read
    result = read_status.mark_content_as_read(db_session, sample_content.id)
    
    assert result is not None
    assert result.session_id == "default"
    assert result.content_id == sample_content.id
    assert isinstance(result.read_at, datetime)


def test_mark_content_as_read_idempotent(db_session: Session, sample_content: Content):
    """Test marking content as read multiple times updates the timestamp."""
    # Mark content as read first time
    result1 = read_status.mark_content_as_read(db_session, sample_content.id)
    first_read_at = result1.read_at
    
    # Mark same content as read again
    result2 = read_status.mark_content_as_read(db_session, sample_content.id)
    
    # Should update the timestamp
    assert result2.read_at >= first_read_at


def test_get_read_content_ids(db_session: Session):
    """Test getting all read content IDs."""
    
    # Create multiple content items
    content_ids = []
    for i in range(3):
        content = Content(
            content_type="article",
            url=f"https://example.com/article{i}",
            title=f"Test Article {i}",
            status="completed",
            content_metadata={"summary": f"Summary {i}"},
        )
        db_session.add(content)
        db_session.commit()
        db_session.refresh(content)
        content_ids.append(content.id)
    
    # Mark first two as read
    read_status.mark_content_as_read(db_session, content_ids[0])
    read_status.mark_content_as_read(db_session, content_ids[1])
    
    # Get read content IDs
    read_ids = read_status.get_read_content_ids(db_session)
    
    assert len(read_ids) == 2
    assert content_ids[0] in read_ids
    assert content_ids[1] in read_ids
    assert content_ids[2] not in read_ids


def test_is_content_read(db_session: Session, sample_content: Content):
    """Test checking if content is read."""
    # Initially not read
    assert not read_status.is_content_read(db_session, sample_content.id)
    
    # Mark as read
    read_status.mark_content_as_read(db_session, sample_content.id)
    
    # Now should be read
    assert read_status.is_content_read(db_session, sample_content.id)


def test_clear_read_status(db_session: Session):
    """Test clearing all read status for a session."""
    session_id = "test_session_123"
    
    # Create and mark multiple content as read
    for i in range(3):
        content = Content(
            content_type="article",
            url=f"https://example.com/article{i}",
            title=f"Test Article {i}",
            status="completed",
            content_metadata={"summary": f"Summary {i}"},
        )
        db_session.add(content)
        db_session.commit()
        read_status.mark_content_as_read(db_session, content.id)
    
    # Verify they are marked as read
    read_ids = read_status.get_read_content_ids(db_session)
    assert len(read_ids) == 3
    
    # Clear read status
    cleared_count = read_status.clear_read_status(db_session, "default")
    assert cleared_count == 3
    
    # Verify all are cleared
    read_ids = read_status.get_read_content_ids(db_session)
    assert len(read_ids) == 0


def test_single_user_read_status(db_session: Session, sample_content: Content):
    """Test that read status works for single user (default session)."""
    # Mark as read
    read_status.mark_content_as_read(db_session, sample_content.id)
    
    # Should be read
    assert read_status.is_content_read(db_session, sample_content.id)
    
    # Clear read status
    cleared_count = read_status.clear_read_status(db_session, "default")
    assert cleared_count == 1
    
    # Should no longer be read
    assert not read_status.is_content_read(db_session, sample_content.id)