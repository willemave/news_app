"""Freeze short-form news eval slices from the local database into JSONL files."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.models.schema import NewsDigest, NewsItem, NewsItemDigestCoverage

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export short-form news eval slices")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tests/evals/news_shortform"),
        help="Directory where JSONL files should be written",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=5000,
        help="Maximum number of news items to consider",
    )
    parser.add_argument(
        "--window-size",
        type=int,
        default=25,
        help="Maximum rows to keep per exported mixed-source window",
    )
    return parser.parse_args()


def _normalize_record(item: NewsItem) -> dict[str, Any]:
    story_url = item.canonical_story_url or item.article_url
    item_url = item.canonical_item_url or item.discussion_url
    return {
        "news_item_id": item.id,
        "legacy_content_id": item.legacy_content_id,
        "visibility_scope": item.visibility_scope,
        "owner_user_id": item.owner_user_id,
        "platform": item.platform,
        "source_type": item.source_type,
        "source_label": item.source_label,
        "source_external_id": item.source_external_id,
        "canonical_item_url": item_url,
        "canonical_story_url": story_url,
        "article_url": item.article_url,
        "article_title": item.article_title,
        "article_domain": item.article_domain,
        "discussion_url": item.discussion_url,
        "summary_title": item.summary_title,
        "summary_key_points": (
            item.summary_key_points if isinstance(item.summary_key_points, list) else []
        ),
        "summary_text": item.summary_text,
        "status": item.status,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "ingested_at": item.ingested_at.isoformat() if item.ingested_at else None,
        "weak_story_key": story_url,
        "weak_item_key": item_url,
        "raw_metadata": dict(item.raw_metadata or {}),
    }


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, default=str))
            handle.write("\n")


def _attach_digest_hints(db, records: list[dict[str, Any]]) -> None:  # noqa: ANN001
    rows = (
        db.query(NewsItemDigestCoverage.news_item_id, NewsDigest.title)
        .join(NewsDigest, NewsDigest.id == NewsItemDigestCoverage.digest_id)
        .all()
    )
    hints_by_item_id: dict[int, list[str]] = defaultdict(list)
    for news_item_id, title in rows:
        if isinstance(title, str) and title:
            hints_by_item_id[int(news_item_id)].append(title)
    for record in records:
        news_item_id = record.get("news_item_id")
        record["weak_digest_titles"] = hints_by_item_id.get(int(news_item_id), [])


def main() -> None:
    setup_logging()
    args = _parse_args()
    output_dir = args.output_dir

    with get_db() as db:
        rows = (
            db.query(NewsItem)
            .order_by(NewsItem.ingested_at.desc(), NewsItem.id.desc())
            .limit(args.max_items)
            .all()
        )
        normalized = [_normalize_record(row) for row in rows]
        _attach_digest_hints(db, normalized)

    exact_duplicates: list[dict[str, Any]] = []
    groups_by_story: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in normalized:
        story_key = record.get("weak_story_key")
        if isinstance(story_key, str) and story_key:
            groups_by_story[story_key].append(record)
    for story_key, records in groups_by_story.items():
        if len(records) < 2:
            continue
        for index, record in enumerate(records, start=1):
            exact_duplicates.append(
                {
                    **record,
                    "slice": "exact_duplicates",
                    "case_id": f"story:{story_key}",
                    "case_position": index,
                    "gold_cluster_id": story_key,
                }
            )

    mixed_source_windows: list[dict[str, Any]] = []
    windows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in normalized:
        ingested_at = record.get("ingested_at")
        if not isinstance(ingested_at, str) or "T" not in ingested_at:
            continue
        window_id = ingested_at[:13]
        windows[window_id].append(record)
    for window_id, records in windows.items():
        platforms = {record.get("platform") for record in records if record.get("platform")}
        if len(platforms) < 2:
            continue
        for index, record in enumerate(records[: args.window_size], start=1):
            mixed_source_windows.append(
                {
                    **record,
                    "slice": "mixed_source_windows",
                    "case_id": window_id,
                    "case_position": index,
                    "gold_cluster_id": record.get("weak_story_key") or record.get("weak_item_key"),
                }
            )

    user_scoped_x_windows: list[dict[str, Any]] = []
    x_windows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in normalized:
        if record.get("platform") != "twitter" or record.get("owner_user_id") is None:
            continue
        ingested_at = record.get("ingested_at")
        if not isinstance(ingested_at, str) or "T" not in ingested_at:
            continue
        window_id = f"user:{record['owner_user_id']}:{ingested_at[:13]}"
        x_windows[window_id].append(record)
    for window_id, records in x_windows.items():
        for index, record in enumerate(records[: args.window_size], start=1):
            user_scoped_x_windows.append(
                {
                    **record,
                    "slice": "user_scoped_x_windows",
                    "case_id": window_id,
                    "case_position": index,
                    "gold_cluster_id": record.get("weak_story_key") or record.get("weak_item_key"),
                }
            )

    _write_jsonl(output_dir / "exact_duplicates.jsonl", exact_duplicates)
    _write_jsonl(output_dir / "mixed_source_windows.jsonl", mixed_source_windows)
    _write_jsonl(output_dir / "user_scoped_x_windows.jsonl", user_scoped_x_windows)

    logger.info(
        "Exported news eval corpus",
        extra={
            "component": "news_eval",
            "operation": "export_corpus",
            "context_data": {
                "exact_duplicates": len(exact_duplicates),
                "mixed_source_windows": len(mixed_source_windows),
                "user_scoped_x_windows": len(user_scoped_x_windows),
                "output_dir": str(output_dir.resolve()),
            },
        },
    )


if __name__ == "__main__":
    main()
