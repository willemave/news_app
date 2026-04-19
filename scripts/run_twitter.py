"""Run scheduled X bookmark sync fan-out.

Legacy entrypoint kept for cron compatibility.

Suggested cron:
*/15 * * * * cd /opt/news_app && /opt/news_app/.venv/bin/python \
scripts/run_twitter.py >> /var/log/news_app/twitter.log 2>&1
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from run_integration_sync import enqueue_x_sync_tasks

from app.core.db import init_db
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run scheduled X bookmark sync work")
    parser.add_argument("--user-id", type=int, default=None, help="Sync one user only")
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Deprecated no-op. Scheduled X feed scraping has been retired.",
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip the private per-user X bookmark sync enqueue",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = _parse_args()
    init_db()

    sync_enqueued = 0

    if not args.skip_sync:
        sync_enqueued = enqueue_x_sync_tasks(user_id=args.user_id)

    logger.info(
        "X scheduler completed: sync_tasks_enqueued=%s",
        sync_enqueued,
    )


if __name__ == "__main__":
    main()
