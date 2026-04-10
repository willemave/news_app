"""Run curated title-clustering eval families against the real relation matcher."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import get_session_factory
from app.core.logging import setup_logging
from app.models.schema import NewsItem
from app.services.news_relations import reconcile_news_item_relation
from tests.services.news_relation_cluster_cases import PRODUCTION_CLUSTER_CASES

EVAL_OWNER_USER_ID = 9_999_999


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate curated title-clustering families with real embeddings"
    )
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        help="Optional case id(s) to run",
    )
    parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Print only failed cases in the text output",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of text",
    )
    return parser.parse_args()


def _make_item(
    *,
    idx: int,
    title: str,
    case_id: str,
    label: str,
    ingested_at: datetime,
) -> NewsItem:
    return NewsItem(
        ingest_key=f"eval-{case_id}-{idx}",
        visibility_scope="user",
        owner_user_id=EVAL_OWNER_USER_ID,
        platform="hackernews",
        source_type="hackernews",
        source_label=f"Source {idx}",
        source_external_id=f"{case_id}-{idx}",
        canonical_item_url=f"https://news.ycombinator.com/item?id={case_id}-{idx}",
        canonical_story_url=f"https://example.com/{case_id}/{idx}",
        article_url=f"https://example.com/{case_id}/{idx}",
        article_title=title,
        article_domain=f"source{idx}.example.com",
        discussion_url=f"https://news.ycombinator.com/item?id={case_id}-{idx}",
        summary_title=title,
        summary_key_points=[label],
        summary_text=f"{label} summary",
        raw_metadata={},
        status="ready",
        ingested_at=ingested_at,
        processed_at=ingested_at,
    )


def _select_cases(case_ids: set[str] | None) -> list[dict[str, Any]]:
    if not case_ids:
        return list(PRODUCTION_CLUSTER_CASES)
    return [case for case in PRODUCTION_CLUSTER_CASES if str(case["case_id"]) in case_ids]


def _evaluate_case(db, case: dict[str, Any]) -> dict[str, Any]:  # noqa: ANN001
    created_ids: list[int] = []
    base_time = datetime.now(UTC).replace(tzinfo=None)
    label = str(case["label"])
    titles = [str(title) for title in case["titles"]]
    case_id = str(case["case_id"])

    for idx, title in enumerate(titles):
        item = _make_item(
            idx=idx,
            title=title,
            case_id=case_id,
            label=label,
            ingested_at=base_time + timedelta(seconds=idx),
        )
        db.add(item)
        db.flush()
        reconcile_news_item_relation(db, news_item_id=item.id)
        created_ids.append(item.id)

    groups: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for item_id in created_ids:
        row = db.get(NewsItem, item_id)
        representative_id = row.representative_news_item_id or row.id
        groups[representative_id].append(
            {
                "id": row.id,
                "representative_id": representative_id,
                "title": row.summary_title or row.article_title,
            }
        )

    largest_cluster = max((len(members) for members in groups.values()), default=0)
    representative_groups = sorted(
        (
            {
                "representative_id": representative_id,
                "member_count": len(members),
                "titles": [member["title"] for member in members],
            }
            for representative_id, members in groups.items()
        ),
        key=lambda group: (-group["member_count"], group["representative_id"]),
    )
    return {
        "case_id": case_id,
        "label": label,
        "expected_member_count": len(titles),
        "largest_cluster": largest_cluster,
        "cluster_count": len(groups),
        "passed": largest_cluster == len(titles),
        "groups": representative_groups,
    }


def _print_text(results: list[dict[str, Any]], *, failures_only: bool) -> None:
    rows = [result for result in results if not failures_only or not result["passed"]]
    passed_count = sum(1 for result in results if result["passed"])
    print(f"Title clustering eval: {passed_count}/{len(results)} passed")
    for result in rows:
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"{status} {result['case_id']} "
            f"largest={result['largest_cluster']}/{result['expected_member_count']} "
            f"clusters={result['cluster_count']} "
            f"{result['label']}"
        )
        if result["passed"]:
            continue
        for group in result["groups"]:
            print(
                f"  rep={group['representative_id']} members={group['member_count']} "
                f"{group['titles'][0]}"
            )


def main() -> int:
    setup_logging()
    args = _parse_args()
    case_ids = set(args.case_ids or [])
    cases = _select_cases(case_ids or None)
    session_factory = get_session_factory()
    results: list[dict[str, Any]] = []

    for case in cases:
        with session_factory() as db:
            results.append(_evaluate_case(db, case))
            db.rollback()

    summary = {
        "case_count": len(results),
        "passed_count": sum(1 for result in results if result["passed"]),
        "failed_count": sum(1 for result in results if not result["passed"]),
        "results": results,
    }

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        _print_text(results, failures_only=args.failures_only)

    return 0 if summary["failed_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
