"""Tests for admin log parsing helpers."""

from __future__ import annotations

from admin.log_parsing import (
    parse_jsonl_record,
    parse_service_log_line,
    record_matches_filters,
)


def test_parse_jsonl_record_round_trips():
    record = parse_jsonl_record(
        '{"timestamp":"2026-03-28T12:00:00Z","component":"queue","context_data":{"task_id":42}}',
        source="structured",
        file_path="structured/test.jsonl",
    )

    assert record is not None
    assert record["component"] == "queue"
    assert record["context_data"]["task_id"] == 42


def test_parse_service_log_line_extracts_suffix_fields():
    record = parse_service_log_line(
        (
            "2026-03-28 12:00:00 - root - INFO - [worker.py:10] - "
            "Task enqueued | component=queue task_id=42 user_id=7"
        ),
        source="workers",
        file_path="/var/log/news_app/workers.log",
    )

    assert record is not None
    assert record["message"] == "Task enqueued"
    assert record["component"] == "queue"
    assert record["task_id"] == "42"
    assert record["user_id"] == "7"


def test_record_matches_filters_uses_context_data_fallback():
    record = {
        "component": "queue",
        "context_data": {"content_id": 99},
    }

    assert record_matches_filters(record, {"component": "queue", "content_id": 99})
