"""Enqueue weekly feed discovery jobs for eligible users."""

from __future__ import annotations

import argparse

from sqlalchemy import func

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.core.settings import get_settings
from app.models.schema import ContentFavorites
from app.services.queue import QueueService, TaskType

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enqueue feed discovery tasks")
    parser.add_argument("--user-id", type=int, default=None)
    parser.add_argument("--min-favorites", type=int, default=None)
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = _parse_args()
    settings = get_settings()
    if args.min_favorites is None:
        min_favorites = max(settings.discovery_min_favorites, 1)
    else:
        min_favorites = max(args.min_favorites, 1)

    queue = QueueService()
    enqueued = 0

    with get_db() as db:
        if args.user_id:
            count = (
                db.query(func.count(ContentFavorites.id))
                .filter(ContentFavorites.user_id == args.user_id)
                .scalar()
                or 0
            )
            if count < min_favorites:
                logger.info(
                    "Skipping user %s (favorites=%s, min=%s)",
                    args.user_id,
                    count,
                    min_favorites,
                )
                return
            queue.enqueue(
                TaskType.DISCOVER_FEEDS,
                payload={"user_id": args.user_id, "trigger": "cron"},
            )
            enqueued = 1
        else:
            rows = (
                db.query(ContentFavorites.user_id)
                .group_by(ContentFavorites.user_id)
                .having(func.count(ContentFavorites.id) >= min_favorites)
                .all()
            )
            user_ids = [row[0] for row in rows]
            for user_id in user_ids:
                queue.enqueue(
                    TaskType.DISCOVER_FEEDS,
                    payload={"user_id": user_id, "trigger": "cron"},
                )
            enqueued = len(user_ids)

    logger.info("Enqueued %s feed discovery tasks", enqueued)


if __name__ == "__main__":
    main()
