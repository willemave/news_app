"""Backfill summary_kind/summary_version in content_metadata.summary."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.constants import (  # noqa: E402
    SUMMARY_KIND_LONG_INTERLEAVED,
    SUMMARY_KIND_LONG_STRUCTURED,
    SUMMARY_KIND_SHORT_NEWS_DIGEST,
    SUMMARY_VERSION_V1,
)


def _run_updates(conn: sqlite3.Connection) -> dict[str, int]:
    cursor = conn.cursor()
    updates = {}

    updates["interleaved_v1"] = cursor.execute(
        """
        UPDATE contents
        SET content_metadata = json_set(
            content_metadata,
            '$.summary_kind', ?,
            '$.summary_version', ?
        )
        WHERE json_type(content_metadata, '$.summary') IS NOT NULL
          AND json_type(content_metadata, '$.summary_kind') IS NULL
          AND json_extract(content_metadata, '$.summary.summary_type') = 'interleaved'
        """,
        (SUMMARY_KIND_LONG_INTERLEAVED, SUMMARY_VERSION_V1),
    ).rowcount

    updates["structured_v1"] = cursor.execute(
        """
        UPDATE contents
        SET content_metadata = json_set(
            content_metadata,
            '$.summary_kind', ?,
            '$.summary_version', ?
        )
        WHERE json_type(content_metadata, '$.summary') IS NOT NULL
          AND json_type(content_metadata, '$.summary_kind') IS NULL
          AND json_type(content_metadata, '$.summary.bullet_points') IS NOT NULL
        """,
        (SUMMARY_KIND_LONG_STRUCTURED, SUMMARY_VERSION_V1),
    ).rowcount

    updates["news_digest_v1"] = cursor.execute(
        """
        UPDATE contents
        SET content_metadata = json_set(
            content_metadata,
            '$.summary_kind', ?,
            '$.summary_version', ?
        )
        WHERE json_type(content_metadata, '$.summary') IS NOT NULL
          AND json_type(content_metadata, '$.summary_kind') IS NULL
          AND json_type(content_metadata, '$.summary.article_url') IS NOT NULL
        """,
        (SUMMARY_KIND_SHORT_NEWS_DIGEST, SUMMARY_VERSION_V1),
    ).rowcount

    conn.commit()
    return updates


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill summary_kind/version in news_app.db")
    parser.add_argument(
        "--db-path",
        default="news_app.db",
        help="Path to SQLite database (default: news_app.db)",
    )
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        updates = _run_updates(conn)
    finally:
        conn.close()

    for key, count in updates.items():
        print(f"{key}: {count}")


if __name__ == "__main__":
    main()
