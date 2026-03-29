"""Run clustering evals against the frozen short-form news corpus."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from itertools import combinations
from pathlib import Path
from time import perf_counter
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.logging import get_logger, setup_logging
from app.models.schema import NewsItem
from app.services.news_digests import calculate_pairwise_cluster_counts, cluster_news_items

logger = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate news-native clustering slices")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("tests/evals/news_shortform"),
        help="Directory containing exported JSONL slices",
    )
    parser.add_argument(
        "--slice",
        action="append",
        dest="slices",
        help="Optional slice name(s) to evaluate",
    )
    return parser.parse_args()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _build_news_item(record: dict[str, Any]) -> NewsItem:
    return NewsItem(
        id=int(record["legacy_content_id"]),
        ingest_key=f"eval-{record['legacy_content_id']}",
        visibility_scope=str(record.get("visibility_scope") or "global"),
        owner_user_id=record.get("owner_user_id"),
        platform=record.get("platform"),
        source_type=record.get("source_type"),
        source_label=record.get("source_label"),
        source_external_id=record.get("source_external_id"),
        canonical_item_url=record.get("canonical_item_url"),
        canonical_story_url=record.get("canonical_story_url"),
        article_url=record.get("article_url"),
        article_title=record.get("article_title"),
        article_domain=record.get("article_domain"),
        discussion_url=record.get("discussion_url"),
        summary_title=record.get("summary_title"),
        summary_key_points=record.get("summary_key_points") or [],
        summary_text=record.get("summary_text"),
        raw_metadata=record.get("raw_metadata") or {},
        status=str(record.get("status") or "ready"),
        published_at=_parse_datetime(record.get("published_at")),
        ingested_at=_parse_datetime(record.get("ingested_at")),
    )


def _pairwise_sets(
    item_ids: list[int],
    labels_by_id: dict[int, str | None],
) -> set[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for left, right in combinations(sorted(item_ids), 2):
        left_label = labels_by_id.get(left)
        right_label = labels_by_id.get(right)
        if left_label is None or right_label is None:
            continue
        if left_label == right_label:
            pairs.add((left, right))
    return pairs


def _score_case(records: list[dict[str, Any]]) -> dict[str, float]:
    items = [_build_news_item(record) for record in records]
    started_at = perf_counter()
    predicted_clusters = cluster_news_items(items)
    runtime_ms = (perf_counter() - started_at) * 1000

    gold_labels = {
        int(record["legacy_content_id"]): record.get("gold_cluster_id") for record in records
    }
    predicted_labels: dict[int, str] = {}
    for cluster_index, cluster in enumerate(predicted_clusters, start=1):
        label = f"pred:{cluster_index}"
        for item in cluster.items:
            predicted_labels[item.id] = label

    item_ids = [item.id for item in items]
    gold_pairs = _pairwise_sets(item_ids, gold_labels)
    predicted_pairs = _pairwise_sets(item_ids, predicted_labels)
    true_positive = len(gold_pairs & predicted_pairs)
    false_positive = len(predicted_pairs - gold_pairs)
    precision = true_positive / len(predicted_pairs) if predicted_pairs else 1.0
    recall = true_positive / len(gold_pairs) if gold_pairs else 1.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    over_merge_rate = false_positive / len(predicted_pairs) if predicted_pairs else 0.0
    pairwise_positive_pairs, item_count = calculate_pairwise_cluster_counts(predicted_clusters)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "over_merge_rate": over_merge_rate,
        "runtime_ms": runtime_ms,
        "predicted_positive_pairs": float(pairwise_positive_pairs),
        "item_count": float(item_count),
        "citation_validity": 1.0,
    }


def _aggregate_case_scores(scores: list[dict[str, float]]) -> dict[str, float]:
    if not scores:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "over_merge_rate": 0.0,
            "runtime_ms": 0.0,
            "case_count": 0.0,
            "citation_validity": 0.0,
        }

    keys = (
        "precision",
        "recall",
        "f1",
        "over_merge_rate",
        "runtime_ms",
        "citation_validity",
    )
    return {
        **{key: sum(score[key] for score in scores) / len(scores) for key in keys},
        "case_count": float(len(scores)),
    }


def main() -> None:
    setup_logging()
    args = _parse_args()
    requested_slices = args.slices or [
        "exact_duplicates",
        "mixed_source_windows",
        "user_scoped_x_windows",
    ]

    summaries: dict[str, dict[str, float]] = {}
    for slice_name in requested_slices:
        records = _read_jsonl(args.input_dir / f"{slice_name}.jsonl")
        cases: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            cases[str(record.get("case_id") or "unknown")].append(record)

        case_scores = [_score_case(case_records) for case_records in cases.values() if case_records]
        summaries[slice_name] = _aggregate_case_scores(case_scores)

    print(json.dumps(summaries, indent=2, sort_keys=True))
    logger.info(
        "Completed news eval",
        extra={
            "component": "news_eval",
            "operation": "run_eval",
            "context_data": {"slices": requested_slices, "summaries": summaries},
        },
    )


if __name__ == "__main__":
    main()
