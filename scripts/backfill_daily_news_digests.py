"""Backfill daily news digests for specific user IDs and date ranges."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
        help="Target user ID. Can be repeated.",
    )
    parser.add_argument(
        "--email",
        type=str,
        action="append",
        dest="emails",
        help="Target user email. Can be repeated.",
    )
    parser.add_argument(
        "--from-date",
        type=str,
        default=None,
        help="Start local date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--to-date",
        type=str,
        default=None,
        help="End local date inclusive (YYYY-MM-DD). Defaults to --from-date.",
    )
    parser.add_argument(
        "--recent-days",
        type=int,
        default=None,
        help="Backfill the last N completed local days per user instead of explicit dates.",
    )
    parser.add_argument(
        "--now-utc",
        type=str,
        default=None,
        help="Override current UTC time (ISO8601) for recent-day calculations.",
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


def _parse_now_utc(raw_value: str | None) -> datetime:
    if not raw_value:
        return datetime.now(UTC)
    parsed = datetime.fromisoformat(raw_value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _resolve_target_dates(
    *,
    timezone_name: str,
    from_date: date | None,
    to_date: date | None,
    recent_days: int | None,
    now_utc: datetime,
) -> tuple[date, date]:
    if recent_days is not None:
        if recent_days <= 0:
            raise ValueError("--recent-days must be >= 1")
        local_today = now_utc.astimezone(ZoneInfo(timezone_name)).date()
        return local_today - timedelta(days=recent_days), local_today - timedelta(days=1)

    if from_date is None:
        raise ValueError("Provide --from-date/--to-date or use --recent-days")

    end_date = to_date or from_date
    if end_date < from_date:
        raise ValueError("--to-date must be >= --from-date")
    return from_date, end_date


def _iter_dates(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def main() -> None:
    setup_logging()
    args = _parse_args()
    now_utc = _parse_now_utc(args.now_utc)

    if args.recent_days is not None and (args.from_date or args.to_date):
        raise ValueError("--recent-days cannot be combined with --from-date/--to-date")

    start_date = _parse_date(args.from_date, flag="--from-date") if args.from_date else None
    end_date = _parse_date(args.to_date, flag="--to-date") if args.to_date else None

    requested_user_ids = sorted({user_id for user_id in (args.user_ids or []) if user_id > 0})
    requested_emails = sorted(
        {
            email.strip().lower()
            for email in (args.emails or [])
            if isinstance(email, str) and email.strip()
        }
    )
    if not requested_user_ids and not requested_emails:
        raise ValueError("At least one --user-id or --email is required")

    logger.info(
        (
            "Starting daily digest backfill user_ids=%s emails=%s "
            "from=%s to=%s recent_days=%s inline=%s force_regenerate=%s now_utc=%s"
        ),
        requested_user_ids,
        requested_emails,
        start_date.isoformat() if start_date else None,
        end_date.isoformat() if end_date else None,
        args.recent_days,
        args.inline,
        args.force_regenerate,
        now_utc.isoformat(),
    )

    processed_users = 0
    processed_days = 0
    enqueued_or_generated = 0
    skipped_missing_users = 0

    with get_db() as db:
        user_filters = []
        if requested_user_ids:
            user_filters.append(User.id.in_(requested_user_ids))
        if requested_emails:
            user_filters.append(func.lower(User.email).in_(requested_emails))

        users = db.query(User).filter(or_(*user_filters)).order_by(User.id.asc()).all()
        users_by_id = {user.id: user for user in users}

        if requested_user_ids:
            for user_id in requested_user_ids:
                if user_id in users_by_id:
                    continue
                skipped_missing_users += 1
                logger.warning("Skipping unknown user_id=%s", user_id)

        found_emails = {str(user.email).strip().lower() for user in users if user.email}
        for email in requested_emails:
            if email in found_emails:
                continue
            skipped_missing_users += 1
            logger.warning("Skipping unknown email=%s", email)

        for user in users:
            if user.id not in users_by_id:
                continue

            processed_users += 1
            timezone_name = normalize_timezone(getattr(user, "news_digest_timezone", None))
            user_start_date, user_end_date = _resolve_target_dates(
                timezone_name=timezone_name,
                from_date=start_date,
                to_date=end_date,
                recent_days=args.recent_days,
                now_utc=now_utc,
            )

            for target_date in _iter_dates(user_start_date, user_end_date):
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
                            "Generated digest inline user=%s email=%s local_date=%s "
                            "digest_id=%s sources=%s created=%s"
                        ),
                        user.id,
                        user.email,
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
                        "Enqueued digest task user=%s email=%s local_date=%s task_id=%s",
                        user.id,
                        user.email,
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
