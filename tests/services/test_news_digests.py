"""Tests for news-native digest grouping and persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from app.models.news_digest_models import NewsDigestBulletDraft, NewsDigestHeaderDraft
from app.models.schema import NewsDigest, NewsDigestBullet, NewsItem, NewsItemDigestCoverage
from app.models.user import User
from app.services import news_digests


def _build_news_item(
    item_id: int,
    *,
    story_url: str,
    item_url: str,
    title: str,
    source_label: str,
) -> NewsItem:
    return NewsItem(
        id=item_id,
        ingest_key=f"item-{item_id}",
        visibility_scope="global",
        owner_user_id=None,
        platform="hackernews",
        source_type="hackernews",
        source_label=source_label,
        source_external_id=str(item_id),
        canonical_item_url=item_url,
        canonical_story_url=story_url,
        article_url=story_url,
        article_title=title,
        article_domain="example.com",
        discussion_url=item_url,
        summary_title=title,
        summary_key_points=["Shared point"],
        summary_text=f"Summary for {title}",
        raw_metadata={},
        status="ready",
        ingested_at=datetime.now(UTC).replace(tzinfo=None),
    )


def test_cluster_news_items_exact_dedupes_shared_story(monkeypatch) -> None:
    monkeypatch.setattr(
        news_digests,
        "encode_news_texts",
        lambda texts: np.eye(len(texts), dtype=np.float32),
    )
    first = _build_news_item(
        1,
        story_url="https://example.com/story",
        item_url="https://news.ycombinator.com/item?id=1",
        title="Same story from HN",
        source_label="Hacker News",
    )
    second = _build_news_item(
        2,
        story_url="https://example.com/story",
        item_url="https://www.reddit.com/r/test/comments/2",
        title="Same story from Reddit",
        source_label="Reddit",
    )
    third = _build_news_item(
        3,
        story_url="https://example.com/other",
        item_url="https://news.ycombinator.com/item?id=3",
        title="Different story",
        source_label="Hacker News",
    )

    clusters = news_digests.cluster_news_items([first, second, third])

    assert len(clusters) == 2
    assert sorted(item.id for item in clusters[0].items) == [1, 2]


def test_generate_news_digest_for_user_persists_bullets_and_coverage(
    db_session,
    monkeypatch,
) -> None:
    user = User(
        apple_id="digest-user",
        email="digest@example.com",
        full_name="Digest User",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    first = _build_news_item(
        11,
        story_url="https://example.com/story-a",
        item_url="https://news.ycombinator.com/item?id=11",
        title="Story A",
        source_label="Hacker News",
    )
    second = _build_news_item(
        12,
        story_url="https://example.com/story-b",
        item_url="https://news.ycombinator.com/item?id=12",
        title="Story B",
        source_label="Hacker News",
    )
    db_session.add_all([first, second])
    db_session.commit()

    monkeypatch.setattr(
        news_digests,
        "cluster_news_items",
        lambda items: [
            news_digests.NewsDigestCluster(items=[items[0]]),
            news_digests.NewsDigestCluster(items=[items[1]]),
        ],
    )
    monkeypatch.setattr(
        news_digests,
        "_generate_bullet_draft",
        lambda cluster: NewsDigestBulletDraft(
            topic=cluster.items[0].summary_title or "Topic",
            details="This cluster contains enough detail for the digest bullet.",
            news_item_ids=[cluster.items[0].id],
        ),
    )
    monkeypatch.setattr(
        news_digests,
        "_generate_header_draft",
        lambda bullets: NewsDigestHeaderDraft(
            title="Morning digest",
            summary="Two distinct stories landed in this run.",
        ),
    )

    result = news_digests.generate_news_digest_for_user(
        db_session,
        user_id=user.id,
        trigger_reason="manual_test",
        force=True,
    )
    db_session.commit()

    assert result.skipped is False
    assert db_session.query(NewsDigest).count() == 1
    assert db_session.query(NewsDigestBullet).count() == 2
    assert db_session.query(NewsItemDigestCoverage).count() == 2


def test_get_news_digest_trigger_decision_flushes_day_rollover(db_session, monkeypatch) -> None:
    user = User(
        apple_id="rollover-user",
        email="rollover@example.com",
        full_name="Rollover User",
        is_active=True,
        news_digest_timezone="US/Pacific",
    )
    db_session.add(user)
    db_session.flush()

    stale_item = NewsItem(
        ingest_key="stale-item",
        visibility_scope="global",
        platform="techmeme",
        source_type="techmeme",
        source_label="Techmeme",
        source_external_id="stale",
        canonical_item_url="https://www.techmeme.com/240101/p1",
        canonical_story_url="https://example.com/stale",
        article_url="https://example.com/stale",
        article_title="Older story",
        article_domain="example.com",
        discussion_url="https://www.techmeme.com/240101/p1",
        summary_title="Older story",
        summary_key_points=["Older point"],
        summary_text="Older summary",
        raw_metadata={},
        status="ready",
        ingested_at=(datetime(2026, 3, 27, 23, 0, tzinfo=UTC) - timedelta(hours=24)).replace(
            tzinfo=None
        ),
    )
    db_session.add(stale_item)
    db_session.commit()

    monkeypatch.setattr(
        news_digests,
        "cluster_news_items",
        lambda items: [news_digests.NewsDigestCluster(items=items)],
    )

    decision = news_digests.get_news_digest_trigger_decision(
        db_session,
        user=user,
        now_utc=datetime(2026, 3, 28, 10, 0, tzinfo=UTC),
    )

    assert decision.should_generate is True
    assert decision.trigger_reason == "day_rollover_flush"
