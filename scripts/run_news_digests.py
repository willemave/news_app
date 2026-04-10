"""Enqueue news-native digest runs for users with uncovered short-form items.

Suggested cron (every 15 minutes):
*/15 * * * * flock -n /tmp/news_app_news_digests.lock /bin/bash -lc \
'cd /opt/news_app && /opt/news_app/.venv/bin/python scripts/run_news_digests.py' \
>> /var/log/news_app/news-digests.log 2>&1
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from time import perf_counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.core.observability import bound_log_context, build_log_extra
from app.models.user import User
from app.services.news_digests import (
    enqueue_news_digest_generation,
    get_news_digest_trigger_decision,
)
from app.services.queue import get_queue_service

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enqueue news-native digest runs")
    parser.add_argument(
        "--user-id",
        type=int,
        action="append",
        dest="user_ids",
        help="Only evaluate specific user IDs. Can be passed multiple times.",
    )
    parser.add_argument(
        "--now-utc",
        type=str,
        default=None,
        help="Override current UTC time (ISO8601) for testing.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log decisions without enqueuing tasks.",
    )
    return parser.parse_args()


def _parse_now_utc(raw_value: str | None) -> datetime:
    if not raw_value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(raw_value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def main() -> None:
    setup_logging()
    args = _parse_args()
    now_utc = _parse_now_utc(args.now_utc)
    started_at = perf_counter()

    considered = 0
    due = 0
    enqueued = 0
    skipped = 0
    backpressure = get_queue_service().get_backpressure_status()

    if bool(backpressure["should_throttle"]):
        logger.warning(
            "Skipping news digest cron run due to queue backpressure",
            extra=build_log_extra(
                component="cron",
                operation="run_news_digests",
                event_name="cron.run",
                status="skipped",
                context_data={
                    "skip_reason": "queue_backpressure",
                    "backpressure": backpressure,
                    "dry_run": args.dry_run,
                    "now_utc": now_utc.isoformat(),
                },
            ),
        )
        return

    with (
        bound_log_context(job_name="run_news_digests", trigger="cron", source="cron"),
        get_db() as db,
    ):
        query = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc())
        if args.user_ids:
            query = query.filter(User.id.in_(args.user_ids))

        for user in query.yield_per(200):
            considered += 1
            decision = get_news_digest_trigger_decision(db, user, now_utc)
            if not decision.should_generate:
                skipped += 1
                continue

            due += 1
            if args.dry_run:
                logger.info(
                    "[dry-run] Would enqueue news digest",
                    extra=build_log_extra(
                        component="cron",
                        operation="run_news_digests",
                        event_name="cron.run",
                        status="skipped",
                        user_id=user.id,
                        context_data={
                            "dry_run": True,
                            "trigger_reason": decision.trigger_reason,
                            "candidate_count": decision.candidate_count,
                            "provisional_group_count": decision.provisional_group_count,
                        },
                    ),
                )
                continue

            task_id = enqueue_news_digest_generation(
                db,
                user.id,
                decision.trigger_reason or "scheduled",
            )
            if task_id is None:
                skipped += 1
                continue
            enqueued += 1

    logger.info(
        "News digest cron completed",
        extra=build_log_extra(
            component="cron",
            operation="run_news_digests",
            event_name="cron.run",
            status="completed",
            duration_ms=(perf_counter() - started_at) * 1000,
            context_data={
                "considered": considered,
                "due": due,
                "enqueued": enqueued,
                "skipped": skipped,
                "dry_run": args.dry_run,
                "now_utc": now_utc.isoformat(),
            },
        ),
    )


if __name__ == "__main__":
    main()
