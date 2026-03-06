"""Backfill daily news digests for specific user IDs and date ranges."""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.models.user import User
from app.services.daily_news_digest import (
    enqueue_daily_news_digest_task,
    normalize_timezone,
    upsert_daily_news_digest_for_user_day,
)

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill daily news digests")
    parser.add_argument(
        "--user-id",
        type=int,
        action="append",
        dest="user_ids",
        required=True,
        help="Target user ID. Can be repeated.",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        required=True,
        help="Start local date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default=None,
        help="End local date inclusive (YYYY-MM-DD). Defaults to --from-date.",
    )
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Generate digests immediately instead of enqueuing tasks.",
    )
    parser.add_argument(
        "--force-regenerate",
        action="store_true",
        help="Regenerate even if digest row already exists.",
    )
    parser.add_argument(
        "--trigger",
        type=str,
        default="backfill",
        help="Trigger label stored in task payload when enqueuing.",
    )
    return parser.parse_args()


def _parse_date(raw_value: str, *, flag: str) -> date:
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise ValueError(f"Invalid {flag}: {raw_value}") from exc


def _iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def main() -> None:
    setup_logging()
    args = _parse_args()

    start_date = _parse_date(args.from_date, flag="--from-date")
    end_date = _parse_date(args.to_date, flag="--to-date") if args.to_date else start_date
    if end_date < start_date:
        raise ValueError("--to-date must be >= --from-date")

    requested_user_ids = sorted({user_id for user_id in args.user_ids if user_id > 0})
    if not requested_user_ids:
        raise ValueError("At least one positive --user-id is required")

    logger.info(
        "Starting daily digest backfill users=%s from=%s to=%s inline=%s force_regenerate=%s",
        requested_user_ids,
        start_date.isoformat(),
        end_date.isoformat(),
        args.inline,
        args.force_regenerate,
    )

    processed_users = 0
    processed_days = 0
    enqueued_or_generated = 0
    skipped_missing_users = 0

    with get_db() as db:
        users = (
            db.query(User)
            .filter(User.id.in_(requested_user_ids))
            .order_by(User.id.asc())
            .all()
        )
        users_by_id = {user.id: user for user in users}

        for user_id in requested_user_ids:
            user = users_by_id.get(user_id)
            if user is None:
                skipped_missing_users += 1
                logger.warning("Skipping unknown user_id=%s", user_id)
                continue

            processed_users += 1
            timezone_name = normalize_timezone(getattr(user, "news_digest_timezone", None))

            for target_date in _iter_dates(start_date, end_date):
                processed_days += 1
                if args.inline:
                    result = upsert_daily_news_digest_for_user_day(
                        db,
                        user_id=user.id,
                        local_date=target_date,
                        timezone_name=timezone_name,
                        force_regenerate=args.force_regenerate,
                    )
                    enqueued_or_generated += 1
                    logger.info(
                        (
                            "Generated digest inline user=%s local_date=%s "
                            "digest_id=%s sources=%s created=%s"
                        ),
                        user.id,
                        target_date.isoformat(),
                        result.digest_id,
                        result.source_count,
                        result.created,
                    )
                    continue

                task_id = enqueue_daily_news_digest_task(
                    db,
                    user_id=user.id,
                    local_date=target_date,
                    timezone_name=timezone_name,
                    trigger=args.trigger,
                    force_regenerate=args.force_regenerate,
                )
                if task_id is not None:
                    enqueued_or_generated += 1
                    logger.info(
                        "Enqueued digest task user=%s local_date=%s task_id=%s",
                        user.id,
                        target_date.isoformat(),
                        task_id,
                    )

    logger.info(
        (
            "Daily digest backfill summary users_processed=%s days_processed=%s "
            "enqueued_or_generated=%s missing_users=%s"
        ),
        processed_users,
        processed_days,
        enqueued_or_generated,
        skipped_missing_users,
    )


if __name__ == "__main__":
    main()
