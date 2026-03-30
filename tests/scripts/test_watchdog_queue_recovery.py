"""Tests for the queue watchdog recovery script."""

from datetime import UTC, datetime, timedelta

from app.models.contracts import TaskQueue, TaskStatus, TaskType
from app.models.schema import ProcessingTask
from scripts.watchdog_queue_recovery import _parse_args, run_watchdog_once


def test_run_watchdog_once_requeues_stale_generate_news_digest(db_session) -> None:
    """Watchdog should requeue stale generate_news_digest tasks."""
    stale_task = ProcessingTask(
        task_type=TaskType.GENERATE_NEWS_DIGEST.value,
        status=TaskStatus.PROCESSING.value,
        payload={"user_id": 1},
        queue_name=TaskQueue.CONTENT.value,
        retry_count=0,
        started_at=datetime.now(UTC) - timedelta(hours=3),
    )
    db_session.add(stale_task)
    db_session.commit()

    result = run_watchdog_once(
        session=db_session,
        transcribe_stale_hours=2.0,
        process_content_stale_hours=2.0,
        generate_news_digest_stale_hours=2.0,
        alert_threshold=99,
        slack_webhook_url=None,
        dry_run=False,
        action_limit=None,
    )
    db_session.commit()
    db_session.refresh(stale_task)

    assert result.requeued_generate_news_digest.touched_count == 1
    assert stale_task.status == TaskStatus.PENDING.value
    assert stale_task.started_at is None
    assert stale_task.completed_at is None
    assert stale_task.retry_count == 1


def test_parse_args_supports_generate_news_digest_stale_hours() -> None:
    """CLI parsing should expose the digest stale-hours option."""
    args = _parse_args(["--generate-news-digest-stale-hours", "4.5"])
    assert args.generate_news_digest_stale_hours == 4.5
