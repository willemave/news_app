"""Tests for usage aggregation and remote log helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from admin.remote_ops import (
    RemoteContext,
    logs_exceptions,
    usage_by_content,
    usage_by_user,
    usage_summary,
)
from app.models.schema import Content, LlmUsageRecord, ProcessingTask
from app.models.user import User
from app.testing.postgres_harness import create_temporary_postgres_harness


@pytest.fixture
def remote_context(tmp_path) -> RemoteContext:
    harness = create_temporary_postgres_harness(
        schema_prefix="newsly_test",
        tables=[
            User.__table__,
            Content.__table__,
            ProcessingTask.__table__,
            LlmUsageRecord.__table__,
        ],
    )
    try:
        with harness.session_factory() as session:
            session.add(
                User(
                    id=1,
                    apple_id="apple-1",
                    email="user@example.com",
                    full_name="User One",
                    is_admin=False,
                    is_active=True,
                )
            )
            session.add(
                Content(
                    id=7,
                    content_type="article",
                    url="https://example.com/article",
                    title="Example Article",
                    status="completed",
                    content_metadata={},
                )
            )
            session.add_all(
                [
                    LlmUsageRecord(
                        provider="openai",
                        model="gpt-5.4-mini",
                        feature="summarization",
                        operation="summarize",
                        source="worker",
                        user_id=1,
                        content_id=7,
                        input_tokens=10,
                        output_tokens=5,
                        total_tokens=15,
                        cost_usd=0.12,
                        currency="USD",
                        pricing_version="2026-03-28",
                        metadata_json={"access_token": "secret"},
                        created_at=datetime(2026, 3, 28, 12, 0, tzinfo=UTC).replace(tzinfo=None),
                    ),
                    LlmUsageRecord(
                        provider="anthropic",
                        model="claude-haiku",
                        feature="summarization",
                        operation="classify",
                        source="worker",
                        user_id=1,
                        content_id=7,
                        input_tokens=6,
                        output_tokens=4,
                        total_tokens=10,
                        cost_usd=0.08,
                        currency="USD",
                        pricing_version="2026-03-28",
                        metadata_json={},
                        created_at=datetime(2026, 3, 28, 12, 5, tzinfo=UTC).replace(tzinfo=None),
                    ),
                ]
            )
            session.commit()
        logs_root = tmp_path / "logs"
        error_logs_dir = logs_root / "errors"
        error_logs_dir.mkdir(parents=True)
        (error_logs_dir / "worker_errors_1.jsonl").write_text(
            "\n".join(
                [
                    (
                        '{"timestamp":"2026-03-30T12:00:00Z","component":"worker",'
                        '"operation":"summarize","error_type":"ValueError",'
                        '"error_message":"new failure"}'
                    ),
                    (
                        '{"timestamp":"2026-03-29T12:00:00Z","component":"worker",'
                        '"operation":"classify","error_type":"RuntimeError",'
                        '"error_message":"older failure"}'
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        yield RemoteContext(
            database_url=harness.database_url,
            logs_dir=logs_root,
            service_log_dir=tmp_path / "service_logs",
        )
    finally:
        harness.close()


def test_usage_summary_groups_by_feature(remote_context):
    summary = usage_summary(remote_context, group_by="feature")

    assert summary["totals"]["call_count"] == 2
    assert summary["totals"]["total_tokens"] == 25
    assert summary["groups"] == [
        {
            "key": "summarization",
            "call_count": 2,
            "input_tokens": 16,
            "output_tokens": 9,
            "total_tokens": 25,
            "cost_usd": 0.2,
        }
    ]


def test_usage_by_user_redacts_metadata(remote_context):
    result = usage_by_user(remote_context, user_id=1)

    assert result["user"]["email"] == "user@example.com"
    assert result["totals"]["call_count"] == 2
    assert any(
        row["metadata"].get("access_token") == "<redacted>" for row in result["rows"]
    )


def test_usage_by_content_includes_content_metadata(remote_context):
    result = usage_by_content(remote_context, content_id=7)

    assert result["content"]["url"] == "https://example.com/article"
    assert result["totals"]["total_tokens"] == 25


def test_logs_exceptions_returns_most_recent_error_records(remote_context):
    result = logs_exceptions(remote_context, limit=1)

    assert result["available"] == 2
    assert result["returned"] == 1
    assert result["exceptions"][0]["error_message"] == "new failure"


def test_logs_exceptions_filters_by_operation(remote_context):
    result = logs_exceptions(remote_context, operation="classify", limit=10)

    assert result["returned"] == 1
    assert result["exceptions"][0]["operation"] == "classify"


def test_logs_exceptions_does_not_require_schema_models(remote_context, monkeypatch):
    def _unexpected_schema_load():
        raise AssertionError("schema models should not load for log-only commands")

    monkeypatch.setattr("admin.remote_ops._load_schema_models", _unexpected_schema_load)

    result = logs_exceptions(remote_context, limit=1)

    assert result["returned"] == 1
