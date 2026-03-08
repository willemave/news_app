"""Regenerate one daily digest row when it fails quality checks.

Usage:
    python scripts/regenerate_daily_digest_if_invalid.py --user-id 1 --local-date 2026-03-06 --apply
"""

from __future__ import annotations

import argparse
from datetime import date

from app.core.db import get_db
from app.models.schema import DailyNewsDigest
from app.services.daily_news_digest import (
    digest_requires_regeneration,
    upsert_daily_news_digest_for_user_day,
)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--user-id", type=int, required=True, help="Digest owner user ID.")
    parser.add_argument(
        "--local-date",
        type=date.fromisoformat,
        required=True,
        help="Digest local date in YYYY-MM-DD format.",
    )
    parser.add_argument(
        "--timezone",
        type=str,
        default=None,
        help="Timezone override; defaults to the existing digest timezone.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist regeneration instead of reporting only.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the digest validation and optional regeneration."""
    args = parse_args()

    with get_db() as db:
        digest = (
            db.query(DailyNewsDigest)
            .filter(
                DailyNewsDigest.user_id == args.user_id,
                DailyNewsDigest.local_date == args.local_date,
            )
            .first()
        )
        timezone_name = args.timezone or (digest.timezone if digest is not None else None)
        if timezone_name is None:
            raise SystemExit("Timezone is required when no existing digest row is present.")

        if digest is not None and not digest_requires_regeneration(digest):
            print("Digest already passes current quality checks; no action needed.")
            return 0

    if not args.apply:
        print("Digest needs regeneration. Re-run with --apply to regenerate it.")
        return 0

    with get_db() as db:
        result = upsert_daily_news_digest_for_user_day(
            db,
            user_id=args.user_id,
            local_date=args.local_date,
            timezone_name=timezone_name,
            force_regenerate=True,
        )

    print(
        "Regenerated digest "
        f"{result.digest_id} for user {args.user_id} on {args.local_date.isoformat()}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
