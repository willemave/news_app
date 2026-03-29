"""Backfill news_items from legacy contents rows and optionally rebuild digest runs."""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.models.contracts import NewsItemStatus
from app.models.schema import (
    NewsDigest,
    NewsDigestBullet,
    NewsDigestBulletSource,
    NewsItem,
    NewsItemDigestCoverage,
)
from app.models.user import User
from app.services.news_digests import (
    enqueue_news_digest_generation,
    get_news_digest_trigger_decision,
)
from app.services.news_ingestion import backfill_news_items_from_contents
from app.services.queue import TaskType, get_queue_service

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill news_items from legacy contents")
    parser.add_argument("--limit", type=int, default=None, help="Optional max rows to backfill")
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Update existing linked rows instead of skipping them",
    )
    parser.add_argument(
        "--enqueue-processing",
        action="store_true",
        help="Enqueue processing for backfilled rows that are not ready yet",
    )
    parser.add_argument(
        "--rebuild-digests",
        action="store_true",
        help="Delete news-native digests and coverage rows before re-enqueuing digest generation",
    )
    parser.add_argument(
        "--enqueue-digests",
        action="store_true",
        help="Evaluate active users and enqueue digest generation after backfill",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = _parse_args()

    with get_db() as db:
        stats = backfill_news_items_from_contents(
            db,
            limit=args.limit,
            only_missing=not args.include_existing,
        )
        logger.info(
            "Backfilled news items",
            extra={
                "component": "news_backfill",
                "operation": "backfill_news_items",
                "context_data": {
                    "created": stats.created,
                    "updated": stats.updated,
                    "skipped": stats.skipped,
                },
            },
        )

        if args.enqueue_processing:
            queue_service = get_queue_service()
            pending_items = (
                db.query(NewsItem)
                .filter(NewsItem.status != NewsItemStatus.READY.value)
                .order_by(NewsItem.id.asc())
                .all()
            )
            for item in pending_items:
                queue_service.enqueue(
                    TaskType.PROCESS_NEWS_ITEM,
                    payload={"news_item_id": item.id},
                    dedupe=False,
                )

        if args.rebuild_digests:
            db.query(NewsDigestBulletSource).delete()
            db.query(NewsDigestBullet).delete()
            db.query(NewsItemDigestCoverage).delete()
            db.query(NewsDigest).delete()
            db.commit()

        if args.enqueue_digests:
            users = db.query(User).filter(User.is_active.is_(True)).order_by(User.id.asc()).all()
            for user in users:
                decision = get_news_digest_trigger_decision(db, user=user)
                if not decision.should_generate:
                    continue
                enqueue_news_digest_generation(
                    db,
                    user_id=user.id,
                    trigger_reason=decision.trigger_reason or "backfill",
                )


if __name__ == "__main__":
    main()
