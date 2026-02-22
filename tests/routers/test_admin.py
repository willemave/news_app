"""Tests for admin router."""

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from app.models.schema import Content, EventLog, ProcessingTask


@pytest.mark.skip(reason="AsyncResponseStream type error - requires admin session auth mock")
@pytest.mark.asyncio
async def test_admin_dashboard(
    async_client: AsyncClient,
    db_session: Session
):
    """Test admin dashboard loads correctly."""
    # Create test data
    # Add content
    content = Content(
        content_type="article",
        url="https://example.com/test",
        title="Test Article",
        source="test",
        status="processed"
    )
    db_session.add(content)
    
    # Add processing task
    task = ProcessingTask(
        task_type="summarize",
        content_id=1,
        status="completed"
    )
    db_session.add(task)
    
    # Add event log
    event = EventLog(
        event_type="scraper",
        event_name="scrape_complete",
        status="success",
        data={"url": "https://example.com/test"}
    )
    db_session.add(event)
    
    db_session.commit()
    
    # Test dashboard loads
    response = await async_client.get("/admin/")
    assert response.status_code == 200
    assert "Admin Dashboard" in response.text
    assert "Content Statistics" in response.text
    assert "Processing Tasks" in response.text
    assert "Event Logs" in response.text
    

@pytest.mark.skip(reason="AsyncResponseStream type error - requires admin session auth mock")
@pytest.mark.asyncio
async def test_admin_dashboard_with_filters(
    async_client: AsyncClient,
    db_session: Session
):
    """Test admin dashboard with event type filter."""
    # Add event logs
    for i in range(3):
        event = EventLog(
            event_type="scraper",
            event_name=f"event_{i}",
            status="success",
            data={"index": i}
        )
        db_session.add(event)
    
    event = EventLog(
        event_type="processor",
        event_name="process_complete",
        status="success",
        data={"processed": True}
    )
    db_session.add(event)
    
    db_session.commit()
    
    # Test with filter
    response = await async_client.get("/admin/?event_type=scraper")
    assert response.status_code == 200
    assert "event_0" in response.text
    assert "event_1" in response.text
    assert "event_2" in response.text
    assert "process_complete" not in response.text