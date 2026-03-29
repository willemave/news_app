"""Tests for strict short-form news processing behavior."""

from __future__ import annotations

from types import SimpleNamespace

from app.models.schema import NewsItem
from app.services.news_processing import process_news_item


def test_process_news_item_fails_on_invalid_summarizer_output(db_session) -> None:
    item = NewsItem(
        ingest_key="news-item-invalid-summary",
        visibility_scope="global",
        platform="hackernews",
        source_type="hackernews",
        source_label="Hacker News",
        source_external_id="123",
        article_url="https://example.com/story",
        article_title="Example story",
        article_domain="example.com",
        discussion_url="https://news.ycombinator.com/item?id=123",
        raw_metadata={"excerpt": "Example excerpt"},
        status="pending",
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    summarizer = SimpleNamespace(summarize=lambda *_args, **_kwargs: {"title": "bad payload"})

    result = process_news_item(
        db_session,
        news_item_id=item.id,
        summarizer=summarizer,
    )

    db_session.refresh(item)
    assert result.success is False
    assert item.status == "failed"
    assert "invalid payload" in (result.error_message or "")
