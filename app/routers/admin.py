"""Admin router for administrative functionality."""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.core.db import get_readonly_db_session
from app.core.deps import require_admin
from app.models.schema import Content, EventLog, OnboardingDiscoveryRun, ProcessingTask
from app.models.user import User
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
TASK_STATUS_ORDER = ("pending", "processing", "failed", "completed")


def _normalize_task_error_type(error_message: str | None) -> str:
    """Map raw task error messages to coarse error buckets."""
    if not error_message:
        return "unknown"

    message = error_message.strip()
    lowered = message.lower()
    if "timeout" in lowered:
        return "timeout"
    if "rate limit" in lowered or "429" in lowered:
        return "rate_limit"
    if "connection" in lowered:
        return "connection"
    if "validation" in lowered:
        return "validation"
    if "json" in lowered:
        return "json_parse"
    if "http" in lowered or "status_code" in lowered:
        return "http_error"

    first_token = message.split(":", maxsplit=1)[0].strip()
    if first_token and first_token[0].isalpha():
        return first_token[:80]
    return "unknown"


def _coerce_event_metric(data: dict[str, Any], key: str) -> int:
    """Read integer metrics from EventLog JSON payload."""
    value = data.get(key)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _build_queue_status_rows(db: Session) -> list[dict[str, Any]]:
    """Build queue partition status rows for dashboard display."""
    queue_status_counts = (
        db.query(
            ProcessingTask.queue_name,
            ProcessingTask.status,
            func.count(ProcessingTask.id).label("count"),
        )
        .group_by(ProcessingTask.queue_name, ProcessingTask.status)
        .all()
    )

    queue_status_map: dict[str, dict[str, int]] = defaultdict(dict)
    for queue_name, status, count in queue_status_counts:
        queue_label = str(queue_name or "unknown")
        queue_status_map[queue_label][str(status or "unknown")] = int(count or 0)

    rows: list[dict[str, Any]] = []
    for queue_name, status_counts in sorted(queue_status_map.items()):
        row: dict[str, Any] = {"queue_name": queue_name}
        total = 0
        for status in TASK_STATUS_ORDER:
            value = int(status_counts.get(status, 0))
            row[status] = value
            total += value
        row["total"] = total
        rows.append(row)
    return rows


def _build_phase_status_rows(db: Session) -> list[dict[str, Any]]:
    """Build task-phase status rows for dashboard display."""
    phase_status_counts = (
        db.query(
            ProcessingTask.task_type,
            ProcessingTask.status,
            func.count(ProcessingTask.id).label("count"),
        )
        .group_by(ProcessingTask.task_type, ProcessingTask.status)
        .all()
    )

    phase_status_map: dict[str, dict[str, int]] = defaultdict(dict)
    for task_type, status, count in phase_status_counts:
        task_label = str(task_type or "unknown")
        phase_status_map[task_label][str(status or "unknown")] = int(count or 0)

    rows: list[dict[str, Any]] = []
    for task_type, status_counts in sorted(phase_status_map.items()):
        row: dict[str, Any] = {"task_type": task_type}
        total = 0
        for status in TASK_STATUS_ORDER:
            value = int(status_counts.get(status, 0))
            row[status] = value
            total += value
        row["total"] = total
        rows.append(row)
    return rows


def _build_recent_failure_rows(
    db: Session, recent_cutoff: datetime
) -> tuple[list[dict[str, Any]], int]:
    """Build recent task failure rollups by phase and normalized error type."""
    recent_failed_tasks = (
        db.query(ProcessingTask.task_type, ProcessingTask.error_message)
        .filter(ProcessingTask.status == "failed")
        .filter(ProcessingTask.completed_at >= recent_cutoff)
        .all()
    )

    failure_buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for task_type, error_message in recent_failed_tasks:
        task_label = str(task_type or "unknown")
        error_label = _normalize_task_error_type(error_message)
        bucket_key = (task_label, error_label)

        bucket = failure_buckets.get(bucket_key)
        if bucket is None:
            bucket = {
                "task_type": task_label,
                "error_type": error_label,
                "count": 0,
                "sample_error": (error_message or "unknown")[:240],
            }
            failure_buckets[bucket_key] = bucket
        bucket["count"] += 1

    rows = sorted(
        failure_buckets.values(),
        key=lambda item: int(item["count"]),
        reverse=True,
    )[:15]
    total = sum(int(item["count"]) for item in rows)
    return rows, total


def _build_scraper_health(db: Session, recent_cutoff: datetime) -> dict[str, Any]:
    """Build scraper run/error aggregates for the dashboard."""
    total_events_24h = (
        db.query(func.count(EventLog.id))
        .filter(EventLog.event_type.like("scraper%"))
        .filter(EventLog.created_at >= recent_cutoff)
        .scalar()
        or 0
    )
    error_events_24h = (
        db.query(func.count(EventLog.id))
        .filter(EventLog.event_type == "scraper_error")
        .filter(EventLog.created_at >= recent_cutoff)
        .scalar()
        or 0
    )
    run_status_rows = (
        db.query(EventLog.status, func.count(EventLog.id).label("count"))
        .filter(EventLog.event_type == "scraper_run")
        .filter(EventLog.created_at >= recent_cutoff)
        .group_by(EventLog.status)
        .all()
    )
    run_status_counts = {
        str(status or "unknown"): int(count or 0) for status, count in run_status_rows
    }

    latest_stats_events = (
        db.query(EventLog)
        .filter(EventLog.event_type == "scraper_stats")
        .filter(EventLog.created_at >= recent_cutoff)
        .order_by(desc(EventLog.created_at))
        .limit(500)
        .all()
    )
    latest_stats_by_name: dict[str, EventLog] = {}
    for event in latest_stats_events:
        scraper_name = str(event.event_name or "unknown")
        if scraper_name not in latest_stats_by_name:
            latest_stats_by_name[scraper_name] = event

    latest_stats_rows = []
    for scraper_name, event in sorted(latest_stats_by_name.items()):
        data = event.data if isinstance(event.data, dict) else {}
        latest_stats_rows.append(
            {
                "scraper_name": scraper_name,
                "scraped": _coerce_event_metric(data, "scraped"),
                "saved": _coerce_event_metric(data, "saved"),
                "duplicates": _coerce_event_metric(data, "duplicates"),
                "errors": _coerce_event_metric(data, "errors"),
                "updated_at": event.created_at,
            }
        )

    error_rows = (
        db.query(EventLog.event_name, func.count(EventLog.id).label("count"))
        .filter(EventLog.event_type == "scraper_error")
        .filter(EventLog.created_at >= recent_cutoff)
        .group_by(EventLog.event_name)
        .order_by(desc(func.count(EventLog.id)))
        .all()
    )
    error_counts = [
        {"scraper_name": str(name or "unknown"), "count": int(count or 0)}
        for name, count in error_rows
    ]

    return {
        "total_events_24h": int(total_events_24h),
        "error_events_24h": int(error_events_24h),
        "run_status_counts": run_status_counts,
        "latest_stats_rows": latest_stats_rows,
        "error_counts": error_counts,
    }


def _build_user_lifecycle(
    db: Session, recent_cutoff: datetime
) -> tuple[dict[str, int], dict[str, int]]:
    """Build user lifecycle and latest onboarding status aggregates."""
    total_users = int(db.query(func.count(User.id)).scalar() or 0)
    active_users = int(
        db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0
    )
    tutorial_completed_users = int(
        db.query(func.count(User.id))
        .filter(User.has_completed_new_user_tutorial.is_(True))
        .scalar()
        or 0
    )
    new_users_24h = int(
        db.query(func.count(User.id)).filter(User.created_at >= recent_cutoff).scalar() or 0
    )
    admin_users = int(
        db.query(func.count(User.id)).filter(User.is_admin.is_(True)).scalar() or 0
    )
    users_with_onboarding = int(
        db.query(func.count(func.distinct(OnboardingDiscoveryRun.user_id))).scalar() or 0
    )

    latest_onboarding_subquery = (
        db.query(
            OnboardingDiscoveryRun.user_id.label("user_id"),
            func.max(OnboardingDiscoveryRun.created_at).label("latest_created_at"),
        )
        .group_by(OnboardingDiscoveryRun.user_id)
        .subquery()
    )
    latest_onboarding_rows = (
        db.query(
            OnboardingDiscoveryRun.status,
            func.count(OnboardingDiscoveryRun.id).label("count"),
        )
        .join(
            latest_onboarding_subquery,
            and_(
                OnboardingDiscoveryRun.user_id == latest_onboarding_subquery.c.user_id,
                OnboardingDiscoveryRun.created_at
                == latest_onboarding_subquery.c.latest_created_at,
            ),
        )
        .group_by(OnboardingDiscoveryRun.status)
        .all()
    )
    latest_onboarding_status_counts = {
        str(status or "unknown"): int(count or 0) for status, count in latest_onboarding_rows
    }

    lifecycle = {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": max(total_users - active_users, 0),
        "tutorial_completed_users": tutorial_completed_users,
        "tutorial_pending_users": max(total_users - tutorial_completed_users, 0),
        "new_users_24h": new_users_24h,
        "admin_users": admin_users,
        "users_with_onboarding": users_with_onboarding,
        "users_without_onboarding": max(total_users - users_with_onboarding, 0),
    }
    return lifecycle, latest_onboarding_status_counts


@router.get("/", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_readonly_db_session)],
    _: None = Depends(require_admin),
    event_type: str | None = None,
    limit: int = 50,
):
    """Admin dashboard with system statistics and event logs."""
    recent_cutoff = datetime.utcnow() - timedelta(hours=24)

    # Content statistics
    content_stats_result = (
        db.query(Content.content_type, func.count(Content.id).label("count"))
        .group_by(Content.content_type)
        .all()
    )
    content_stats = {row.content_type: row.count for row in content_stats_result}
    total_content = db.query(func.count(Content.id)).scalar() or 0

    # Task statistics
    task_stats_result = (
        db.query(ProcessingTask.status, func.count(ProcessingTask.id).label("count"))
        .group_by(ProcessingTask.status)
        .all()
    )
    task_stats = {row.status: row.count for row in task_stats_result}
    total_tasks = db.query(func.count(ProcessingTask.id)).scalar() or 0
    recent_tasks = (
        db.query(func.count(ProcessingTask.id))
        .filter(ProcessingTask.created_at >= recent_cutoff)
        .scalar()
        or 0
    )

    # Dashboard readouts
    queue_status_rows = _build_queue_status_rows(db)
    phase_status_rows = _build_phase_status_rows(db)
    recent_failure_rows, recent_failure_total = _build_recent_failure_rows(db, recent_cutoff)
    scraper_health = _build_scraper_health(db, recent_cutoff)
    user_stats, onboarding_latest_status_counts = _build_user_lifecycle(db, recent_cutoff)

    # Event logs with optional filtering
    event_logs_query = db.query(EventLog).order_by(desc(EventLog.created_at))
    if event_type:
        event_logs_query = event_logs_query.filter(EventLog.event_type == event_type)
    event_logs = event_logs_query.limit(limit).all()

    event_types_result = db.query(EventLog.event_type).distinct().all()
    event_types = [row[0] for row in event_types_result if row[0]]

    # Content with missing summary and explicit errors
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
            "queue_status_rows": queue_status_rows,
            "phase_status_rows": phase_status_rows,
            "recent_failure_rows": recent_failure_rows,
            "recent_failure_total": recent_failure_total,
            "scraper_total_events_24h": scraper_health["total_events_24h"],
            "scraper_error_events_24h": scraper_health["error_events_24h"],
            "scraper_run_status_counts": scraper_health["run_status_counts"],
            "scraper_latest_stats": scraper_health["latest_stats_rows"],
            "scraper_error_counts": scraper_health["error_counts"],
            "user_stats": user_stats,
            "onboarding_latest_status_counts": onboarding_latest_status_counts,
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
