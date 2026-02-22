"""Tests for news summary schema strictness."""

from __future__ import annotations

from app.models.metadata import NewsSummary


def test_news_summary_ignores_legacy_fields(caplog) -> None:
    """Legacy fields are ignored for news summary payloads."""
    payload = {
        "title": "Legacy Digest Title",
        "overview": "Legacy overview text.",
        "bullet_points": ["Point one", "Point two"],
    }

    summary = NewsSummary.model_validate(payload)

    assert summary.summary is None
    assert summary.key_points == []
    assert not caplog.records
