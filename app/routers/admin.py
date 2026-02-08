"""Admin router for administrative functionality."""

from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from app.core.db import get_readonly_db_session
from app.core.deps import require_admin
from app.models.schema import Content, EventLog, ProcessingTask
from app.routers.api.models import (
    OnboardingAudioDiscoverRequest,
    OnboardingAudioLanePreviewResponse,
)
from app.services.admin_eval import (
    EVAL_MODEL_LABELS,
    EVAL_MODEL_SPECS,
    LONGFORM_TEMPLATE_LABELS,
    AdminEvalRunRequest,
    get_default_pricing,
    run_admin_eval,
)
from app.services.onboarding import preview_audio_lane_plan

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_readonly_db_session)],
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


@router.get("/onboarding/lane-preview", response_class=HTMLResponse)
def onboarding_lane_preview_page(
    request: Request,
    _: None = Depends(require_admin),
) -> HTMLResponse:
    """Render admin tool for onboarding lane preview."""
    return templates.TemplateResponse(
        "admin_onboarding_lane_preview.html",
        {
            "request": request,
        },
    )


@router.post(
    "/onboarding/lane-preview",
    response_model=OnboardingAudioLanePreviewResponse,
)
async def onboarding_lane_preview(
    payload: OnboardingAudioDiscoverRequest,
    _: None = Depends(require_admin),
) -> OnboardingAudioLanePreviewResponse:
    """Preview generated onboarding lanes from transcript input."""
    try:
        return await preview_audio_lane_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/evals/summaries", response_class=HTMLResponse)
def admin_eval_summaries_page(
    request: Request,
    _: None = Depends(require_admin),
) -> HTMLResponse:
    """Render admin summary eval UI."""
    return templates.TemplateResponse(
        "admin_eval_summaries.html",
        {
            "request": request,
            "model_specs": EVAL_MODEL_SPECS,
            "model_labels": EVAL_MODEL_LABELS,
            "template_labels": LONGFORM_TEMPLATE_LABELS,
            "default_pricing": get_default_pricing(),
        },
    )


@router.post("/evals/summaries/run")
def admin_eval_summaries_run(
    payload: AdminEvalRunRequest,
    db: Annotated[Session, Depends(get_readonly_db_session)],
    _: None = Depends(require_admin),
) -> dict[str, Any]:
    """Run summary/title eval against selected models and content samples."""
    return run_admin_eval(db, payload)
