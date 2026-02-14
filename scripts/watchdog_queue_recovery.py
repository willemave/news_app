#!/usr/bin/env python3
"""Automated queue watchdog for recovery actions.

Runs the same safety actions operators have been running manually:
1. Move transcribe tasks into the dedicated transcribe queue.
2. Requeue stale transcribe processing tasks.
3. Requeue stale process_content processing tasks.

The script supports one-shot mode (cron) and loop mode (supervisor/systemd).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory for local imports.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import get_logger, setup_logging  # noqa: E402
from app.core.settings import get_settings  # noqa: E402
from app.models.schema import EventLog, ProcessingTask  # noqa: E402
from app.services.queue import TaskQueue, TaskStatus, TaskType  # noqa: E402

logger = get_logger(__name__)

PROCESSING_TIMESTAMP_EXPR = func.coalesce(
    ProcessingTask.started_at,
    ProcessingTask.completed_at,
    ProcessingTask.created_at,
)


@dataclass
class ActionResult:
    """Result for a single watchdog action."""

    action_name: str
    touched_count: int
    task_ids: list[int]
    metadata: dict[str, Any]


@dataclass
class WatchdogRunResult:
    """Top-level watchdog result payload."""

    started_at: datetime
    finished_at: datetime
    dry_run: bool
    moved_transcribe: ActionResult
    requeued_transcribe: ActionResult
    requeued_process_content: ActionResult

    @property
    def total_touched(self) -> int:
        """Return the total touched tasks across all actions."""
        return (
            self.moved_transcribe.touched_count
            + self.requeued_transcribe.touched_count
            + self.requeued_process_content.touched_count
        )


def _env_float(name: str, default: float) -> float:
    """Read a float from env with fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid float env %s=%s, using default=%s", name, value, default)
        return default


def _env_int(name: str, default: int) -> int:
    """Read an int from env with fallback."""
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid int env %s=%s, using default=%s", name, value, default)
        return default


def _create_session_factory(database_url: str | None = None) -> tuple[sessionmaker, str]:
    """Create DB session factory from explicit URL or settings."""
    effective_database_url = database_url or str(get_settings().database_url)
    engine = create_engine(effective_database_url)
    return sessionmaker(bind=engine, autocommit=False, autoflush=False), effective_database_url


def _move_transcribe_tasks(
    session: Session,
    *,
    dry_run: bool,
    limit: int | None,
) -> ActionResult:
    """Move transcribe tasks to the transcribe queue."""
    query = (
        session.query(ProcessingTask)
        .filter(ProcessingTask.task_type == TaskType.TRANSCRIBE.value)
        .filter(
            ProcessingTask.status.in_(
                [TaskStatus.PENDING.value, TaskStatus.PROCESSING.value]
            )
        )
        .filter(ProcessingTask.queue_name != TaskQueue.TRANSCRIBE.value)
        .order_by(ProcessingTask.id.asc())
    )
    if limit:
        query = query.limit(limit)

    rows = query.all()
    task_ids = [int(row.id) for row in rows]

    if not dry_run:
        for row in rows:
            row.queue_name = TaskQueue.TRANSCRIBE.value

    return ActionResult(
        action_name="move_transcribe",
        touched_count=len(rows),
        task_ids=task_ids,
        metadata={
            "target_queue": TaskQueue.TRANSCRIBE.value,
            "statuses": [TaskStatus.PENDING.value, TaskStatus.PROCESSING.value],
            "limit": limit,
        },
    )


def _requeue_stale_tasks(
    session: Session,
    *,
    task_type: TaskType,
    stale_hours: float,
    dry_run: bool,
    limit: int | None,
) -> ActionResult:
    """Requeue stale processing tasks for a given task type."""
    cutoff = datetime.now(UTC) - timedelta(hours=stale_hours)
    query = (
        session.query(ProcessingTask)
        .filter(ProcessingTask.status == TaskStatus.PROCESSING.value)
        .filter(ProcessingTask.task_type == task_type.value)
        .filter(cutoff >= PROCESSING_TIMESTAMP_EXPR)
        .order_by(PROCESSING_TIMESTAMP_EXPR.asc(), ProcessingTask.id.asc())
    )
    if limit:
        query = query.limit(limit)

    rows = query.all()
    task_ids = [int(row.id) for row in rows]

    if not dry_run:
        now = datetime.now(UTC)
        for row in rows:
            row.status = TaskStatus.PENDING.value
            row.started_at = None
            row.completed_at = None
            row.created_at = now
            row.error_message = None
            row.retry_count = int(row.retry_count or 0) + 1

    return ActionResult(
        action_name=f"requeue_stale_{task_type.value}",
        touched_count=len(rows),
        task_ids=task_ids,
        metadata={
            "task_type": task_type.value,
            "stale_hours": stale_hours,
            "limit": limit,
        },
    )


def _record_watchdog_events(session: Session, result: WatchdogRunResult) -> None:
    """Persist watchdog action/run events into EventLog."""
    run_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")

    action_results = [
        result.moved_transcribe,
        result.requeued_transcribe,
        result.requeued_process_content,
    ]
    for action in action_results:
        session.add(
            EventLog(
                event_type="queue_watchdog_action",
                event_name=action.action_name,
                status="completed",
                data={
                    "run_id": run_id,
                    "touched_count": action.touched_count,
                    "task_ids": action.task_ids[:100],
                    "metadata": action.metadata,
                },
            )
        )

    session.add(
        EventLog(
            event_type="queue_watchdog_run",
            event_name="queue_recovery",
            status="completed",
            data={
                "run_id": run_id,
                "started_at": result.started_at.isoformat(),
                "finished_at": result.finished_at.isoformat(),
                "duration_seconds": max(
                    (result.finished_at - result.started_at).total_seconds(),
                    0.0,
                ),
                "total_touched": result.total_touched,
                "moved_transcribe": result.moved_transcribe.touched_count,
                "requeued_transcribe": result.requeued_transcribe.touched_count,
                "requeued_process_content": result.requeued_process_content.touched_count,
                "dry_run": result.dry_run,
            },
        )
    )


def _send_slack_alert(webhook_url: str, result: WatchdogRunResult) -> tuple[bool, str]:
    """Send a concise Slack alert for touched watchdog actions."""
    payload = {
        "text": (
            "Queue watchdog touched tasks"
            f" | total={result.total_touched}"
            f" move_transcribe={result.moved_transcribe.touched_count}"
            f" requeue_transcribe={result.requeued_transcribe.touched_count}"
            f" requeue_process_content={result.requeued_process_content.touched_count}"
        )
    }

    try:
        response = httpx.post(webhook_url, json=payload, timeout=10.0)
        response.raise_for_status()
        return True, "sent"
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to send watchdog Slack alert: %s", exc)
        return False, str(exc)


def _record_watchdog_alert_event(
    session: Session,
    *,
    result: WatchdogRunResult,
    status: str,
    detail: str,
    threshold: int,
) -> None:
    """Persist Slack alert attempt outcome for dashboard visibility."""
    session.add(
        EventLog(
            event_type="queue_watchdog_alert",
            event_name="slack",
            status=status,
            data={
                "total_touched": result.total_touched,
                "alert_threshold": threshold,
                "detail": detail,
            },
        )
    )


def run_watchdog_once(
    *,
    session: Session,
    transcribe_stale_hours: float,
    process_content_stale_hours: float,
    alert_threshold: int,
    slack_webhook_url: str | None,
    dry_run: bool,
    action_limit: int | None,
) -> WatchdogRunResult:
    """Execute one watchdog cycle and optionally persist/alert."""
    started_at = datetime.now(UTC)

    moved_transcribe = _move_transcribe_tasks(
        session,
        dry_run=dry_run,
        limit=action_limit,
    )
    requeued_transcribe = _requeue_stale_tasks(
        session,
        task_type=TaskType.TRANSCRIBE,
        stale_hours=transcribe_stale_hours,
        dry_run=dry_run,
        limit=action_limit,
    )
    requeued_process_content = _requeue_stale_tasks(
        session,
        task_type=TaskType.PROCESS_CONTENT,
        stale_hours=process_content_stale_hours,
        dry_run=dry_run,
        limit=action_limit,
    )

    finished_at = datetime.now(UTC)
    result = WatchdogRunResult(
        started_at=started_at,
        finished_at=finished_at,
        dry_run=dry_run,
        moved_transcribe=moved_transcribe,
        requeued_transcribe=requeued_transcribe,
        requeued_process_content=requeued_process_content,
    )

    if dry_run:
        return result

    _record_watchdog_events(session, result)

    if result.total_touched < alert_threshold:
        return result

    if not slack_webhook_url:
        _record_watchdog_alert_event(
            session,
            result=result,
            status="skipped",
            detail="No QUEUE_WATCHDOG_SLACK_WEBHOOK_URL configured",
            threshold=alert_threshold,
        )
        return result

    sent, detail = _send_slack_alert(slack_webhook_url, result)
    _record_watchdog_alert_event(
        session,
        result=result,
        status="sent" if sent else "failed",
        detail=detail,
        threshold=alert_threshold,
    )
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse watchdog CLI arguments."""
    parser = argparse.ArgumentParser(description="Queue recovery watchdog")
    parser.add_argument(
        "--database-url",
        help="Override database URL instead of using app settings/.env",
    )
    parser.add_argument(
        "--transcribe-stale-hours",
        type=float,
        default=_env_float("QUEUE_WATCHDOG_TRANSCRIBE_STALE_HOURS", 2.0),
        help="Requeue transcribe processing tasks older than this many hours",
    )
    parser.add_argument(
        "--process-content-stale-hours",
        type=float,
        default=_env_float("QUEUE_WATCHDOG_PROCESS_CONTENT_STALE_HOURS", 2.0),
        help="Requeue process_content processing tasks older than this many hours",
    )
    parser.add_argument(
        "--alert-threshold",
        type=int,
        default=_env_int("QUEUE_WATCHDOG_ALERT_THRESHOLD", 1),
        help="Alert only when touched task total is >= threshold",
    )
    parser.add_argument(
        "--slack-webhook-url",
        default=os.getenv("QUEUE_WATCHDOG_SLACK_WEBHOOK_URL"),
        help="Optional Slack webhook URL for watchdog alerts",
    )
    parser.add_argument(
        "--action-limit",
        type=int,
        default=None,
        help="Cap rows touched per action for safety",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously with sleep interval between cycles",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Loop interval in seconds (default: 300)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview only; no writes")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def _print_result(result: WatchdogRunResult) -> None:
    """Print watchdog run summary."""
    print("Queue watchdog run summary")
    print(f"  started_at: {result.started_at.isoformat()}")
    print(f"  finished_at: {result.finished_at.isoformat()}")
    print(f"  dry_run: {result.dry_run}")
    print(f"  move_transcribe: {result.moved_transcribe.touched_count}")
    print(f"  requeue_stale_transcribe: {result.requeued_transcribe.touched_count}")
    print(
        "  requeue_stale_process_content: "
        f"{result.requeued_process_content.touched_count}"
    )
    print(f"  total_touched: {result.total_touched}")


def main(argv: list[str] | None = None) -> int:
    """Run the queue watchdog in one-shot or loop mode."""
    args = _parse_args(argv)
    setup_logging(level="DEBUG" if args.debug else "INFO")

    session_factory, effective_database_url = _create_session_factory(args.database_url)
    logger.info("Queue watchdog targeting database: %s", effective_database_url)

    def _run_cycle() -> int:
        with session_factory() as session:
            try:
                result = run_watchdog_once(
                    session=session,
                    transcribe_stale_hours=float(args.transcribe_stale_hours),
                    process_content_stale_hours=float(args.process_content_stale_hours),
                    alert_threshold=max(int(args.alert_threshold), 1),
                    slack_webhook_url=args.slack_webhook_url,
                    dry_run=bool(args.dry_run),
                    action_limit=args.action_limit,
                )
                if not args.dry_run:
                    session.commit()
                _print_result(result)
                return 0
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                logger.exception("Queue watchdog cycle failed: %s", exc)
                if not args.dry_run:
                    session.add(
                        EventLog(
                            event_type="queue_watchdog_run",
                            event_name="queue_recovery",
                            status="failed",
                            data={
                                "error": str(exc),
                                "error_type": type(exc).__name__,
                            },
                        )
                    )
                    session.commit()
                return 1

    if not args.loop:
        return _run_cycle()

    exit_code = 0
    interval_seconds = max(int(args.interval_seconds), 30)
    logger.info("Starting watchdog loop interval=%ss", interval_seconds)

    try:
        while True:
            cycle_code = _run_cycle()
            if cycle_code != 0:
                exit_code = cycle_code
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Queue watchdog loop interrupted by user")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
