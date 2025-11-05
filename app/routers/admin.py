"""Admin router for administrative functionality."""

from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.db import get_db_session
from app.core.deps import require_admin
from app.models.schema import Content, EventLog, ProcessingTask

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db_session)],
    _: None = Depends(require_admin),
    event_type: str | None = None,
    limit: int = 50,
):
    """Admin dashboard with system statistics and event logs."""

    # Get content statistics
    content_stats_result = (
        db.query(Content.content_type, func.count(Content.id).label("count"))
        .group_by(Content.content_type)
        .all()
    )
    content_stats = {row.content_type: row.count for row in content_stats_result}

    # Get total content count
    total_content = db.query(func.count(Content.id)).scalar() or 0

    # Get processing task statistics
    task_stats_result = (
        db.query(ProcessingTask.status, func.count(ProcessingTask.id).label("count"))
        .group_by(ProcessingTask.status)
        .all()
    )
    task_stats = {row.status: row.count for row in task_stats_result}

    # Get total tasks count
    total_tasks = db.query(func.count(ProcessingTask.id)).scalar() or 0

    # Get recent tasks (last 24 hours)
    recent_cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_tasks = (
        db.query(func.count(ProcessingTask.id))
        .filter(ProcessingTask.created_at >= recent_cutoff)
        .scalar()
        or 0
    )

    # Get event logs with optional filtering
    event_logs_query = db.query(EventLog).order_by(desc(EventLog.created_at))

    if event_type:
        event_logs_query = event_logs_query.filter(EventLog.event_type == event_type)

    event_logs = event_logs_query.limit(limit).all()

    # Get unique event types for filter
    event_types_result = db.query(EventLog.event_type).distinct().all()
    event_types = [row[0] for row in event_types_result if row[0]]

    # Get content without summaries (with error messages)
    content_without_summary = (
        db.query(Content)
        .filter(
            (Content.content_metadata["summary"].is_(None))
            | (Content.content_metadata["summary"] == "null")
        )
        .filter(Content.error_message.is_not(None))
        .order_by(desc(Content.created_at))
        .limit(20)
        .all()
    )

    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "content_stats": content_stats,
            "total_content": total_content,
            "task_stats": task_stats,
            "total_tasks": total_tasks,
            "recent_tasks": recent_tasks,
            "event_logs": event_logs,
            "event_types": event_types,
            "selected_event_type": event_type,
            "limit": limit,
            "content_without_summary": content_without_summary,
        },
    )
