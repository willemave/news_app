"""
Simple event logging service for tracking all system events, stats, and errors.
"""

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.schema import EventLog

logger = get_logger(__name__)


def log_event(
    event_type: str, event_name: str | None = None, status: str | None = None, **data: Any
) -> int:
    """
    Log any event with arbitrary data.

    Args:
        event_type: Type of event (e.g., 'scraper_run', 'processing_error', 'system_metric')
        event_name: Optional name/identifier (e.g., 'hackernews', 'pdf_processor')
        status: Optional status (e.g., 'started', 'completed', 'failed')
        **data: Any additional data to store as JSON

    Returns:
        The ID of the created event log entry
    """
    try:
        with get_db() as db:
            event = EventLog(event_type=event_type, event_name=event_name, status=status, data=data)
            db.add(event)
            db.commit()
            db.refresh(event)
            return event.id
    except Exception as e:
        logger.exception(
            "Failed to log event %s/%s: %s",
            event_type,
            event_name,
            e,
            extra={
                "component": "event_logger",
                "operation": "log_event",
                "context_data": {"event_type": event_type, "event_name": event_name},
            },
        )
        raise


@contextmanager
def track_event(event_type: str, event_name: str | None = None, **initial_data: Any):
    """
    Context manager for tracking events with automatic start/end times and status.

    Args:
        event_type: Type of event to track
        event_name: Optional name/identifier
        **initial_data: Initial data to include in the start event

    Yields:
        The event ID of the start event

    Example:
        with track_event("scraper_run", "hackernews", config={"max_items": 100}) as event_id:
            # Run scraper
            stats = scraper.run()
            # Log additional data
            log_event("scraper_stats", "hackernews", parent_event_id=event_id, **stats)
    """
    start_time = datetime.utcnow()

    # Log start event
    event_id = log_event(
        event_type=event_type,
        event_name=event_name,
        status="started",
        started_at=start_time.isoformat(),
        **initial_data,
    )

    try:
        yield event_id

        # Success - log completion
        duration = (datetime.utcnow() - start_time).total_seconds()
        log_event(
            event_type=event_type,
            event_name=event_name,
            status="completed",
            event_id=event_id,
            duration_seconds=duration,
            completed_at=datetime.utcnow().isoformat(),
            started_at=start_time.isoformat(),
        )

    except Exception as e:
        # Failure - log error
        duration = (datetime.utcnow() - start_time).total_seconds()
        log_event(
            event_type=event_type,
            event_name=event_name,
            status="failed",
            event_id=event_id,
            duration_seconds=duration,
            error=str(e),
            error_type=type(e).__name__,
            completed_at=datetime.utcnow().isoformat(),
            started_at=start_time.isoformat(),
        )
        raise


def get_recent_events(
    event_type: str | None = None,
    event_name: str | None = None,
    status: str | None = None,
    limit: int = 10,
    hours: int | None = None,
) -> list[EventLog]:
    """
    Get recent events with optional filtering.

    Args:
        event_type: Filter by event type
        event_name: Filter by event name
        status: Filter by status
        limit: Maximum number of events to return
        hours: Only get events from the last N hours

    Returns:
        List of EventLog entries
    """
    with get_db() as db:
        query = db.query(EventLog)

        if event_type:
            query = query.filter(EventLog.event_type == event_type)
        if event_name:
            query = query.filter(EventLog.event_name == event_name)
        if status:
            query = query.filter(EventLog.status == status)
        if hours:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(EventLog.created_at >= cutoff)

        return query.order_by(EventLog.created_at.desc()).limit(limit).all()


def get_event_stats(event_type: str, hours: int = 24) -> dict[str, Any]:
    """
    Get statistics for a specific event type over a time period.

    Args:
        event_type: The event type to get stats for
        hours: Time period in hours (default: 24)

    Returns:
        Dictionary with counts by status and other stats
    """
    from datetime import timedelta

    from sqlalchemy import func

    with get_db() as db:
        cutoff = datetime.utcnow() - timedelta(hours=hours)

        # Get counts by status
        status_counts = (
            db.query(EventLog.status, func.count(EventLog.id).label("count"))
            .filter(EventLog.event_type == event_type, EventLog.created_at >= cutoff)
            .group_by(EventLog.status)
            .all()
        )

        # Get total count
        total_count = (
            db.query(func.count(EventLog.id))
            .filter(EventLog.event_type == event_type, EventLog.created_at >= cutoff)
            .scalar()
        )

        return {
            "event_type": event_type,
            "time_period_hours": hours,
            "total_count": total_count or 0,
            "status_counts": {status: count for status, count in status_counts},
            "cutoff_time": cutoff.isoformat(),
        }
