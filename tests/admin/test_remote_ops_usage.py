"""Tests for usage aggregation helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from admin.remote_ops import RemoteContext, usage_by_content, usage_by_user, usage_summary
from app.core.db import Base
from app.models.schema import Content, LlmUsageRecord, ProcessingTask
from app.models.user import User


def _build_context(tmp_path) -> RemoteContext:
    db_path = tmp_path / "usage.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__,
            Content.__table__,
            ProcessingTask.__table__,
            LlmUsageRecord.__table__,
        ],
    )
    with Session(engine) as session:
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
    engine.dispose()
    return RemoteContext(
        database_url=f"sqlite:///{db_path}",
        logs_dir=tmp_path / "logs",
        service_log_dir=tmp_path / "service_logs",
    )


def test_usage_summary_groups_by_feature(tmp_path):
    context = _build_context(tmp_path)

    summary = usage_summary(context, group_by="feature")

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


def test_usage_by_user_redacts_metadata(tmp_path):
    context = _build_context(tmp_path)

    result = usage_by_user(context, user_id=1)

    assert result["user"]["email"] == "user@example.com"
    assert result["totals"]["call_count"] == 2
    assert any(
        row["metadata"].get("access_token") == "<redacted>" for row in result["rows"]
    )


def test_usage_by_content_includes_content_metadata(tmp_path):
    context = _build_context(tmp_path)

    result = usage_by_content(context, content_id=7)

    assert result["content"]["url"] == "https://example.com/article"
    assert result["totals"]["total_tokens"] == 25
