"""Tests for representative news-item clustering and enrichment."""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from app.models.schema import NewsItem, NewsItemReadStatus
from app.services.news_feed import count_unread_news_items
from app.services.news_relations import (
    SEMANTIC_PREFILTER_MAX_CANDIDATES,
    reconcile_news_item_relation,
)


def _news_item(
    db_session,
    *,
    ingest_key: str,
    source_external_id: str,
    title: str,
    story_url: str,
) -> NewsItem:
    item = NewsItem(
        ingest_key=ingest_key,
        visibility_scope="global",
        platform="hackernews",
        source_type="hackernews",
        source_label="Hacker News",
        source_external_id=source_external_id,
        canonical_item_url=f"https://news.ycombinator.com/item?id={source_external_id}",
        canonical_story_url=story_url,
        article_url=story_url,
        article_title=title,
        article_domain="example.com",
        discussion_url=f"https://news.ycombinator.com/item?id={source_external_id}",
        summary_title=title,
        summary_key_points=["Key point"],
        summary_text=f"{title} summary",
        raw_metadata={},
        status="ready",
        ingested_at=datetime.now(UTC).replace(tzinfo=None),
        processed_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db_session.add(item)
    db_session.flush()
    return item


def test_reconcile_news_item_relation_suppresses_exact_duplicate_and_keeps_unread_count_stable(
    db_session,
    test_user,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "app.services.news_relations.encode_news_texts",
        lambda texts: np.eye(len(texts), dtype=float),
    )

    representative = _news_item(
        db_session,
        ingest_key="rep",
        source_external_id="100",
        title="OpenAI ships new feature",
        story_url="https://example.com/story-1",
    )
    reconcile_news_item_relation(db_session, news_item_id=representative.id)
    db_session.add(
        NewsItemReadStatus(
            user_id=test_user.id,
            news_item_id=representative.id,
            read_at=datetime.now(UTC).replace(tzinfo=None),
        )
    )
    db_session.commit()

    duplicate = _news_item(
        db_session,
        ingest_key="dup",
        source_external_id="101",
        title="OpenAI ships new feature again",
        story_url="https://example.com/story-1",
    )
    reconcile_news_item_relation(db_session, news_item_id=duplicate.id)
    db_session.commit()

    db_session.refresh(representative)
    db_session.refresh(duplicate)
    assert duplicate.representative_news_item_id == representative.id
    assert representative.cluster_size == 2
    assert representative.raw_metadata["cluster"]["member_ids"] == [representative.id, duplicate.id]
    assert count_unread_news_items(db_session, user_id=test_user.id) == 0


def test_reconcile_news_item_relation_uses_secondary_threshold_with_lexical_guard(
    db_session,
    monkeypatch,
) -> None:
    def fake_encode(_texts: list[str]) -> np.ndarray:
        return np.array(
            [
                [1.0, 0.0],
                [0.77, 0.63],
            ],
            dtype=float,
        )

    monkeypatch.setattr("app.services.news_relations.encode_news_texts", fake_encode)

    representative = _news_item(
        db_session,
        ingest_key="rep-secondary",
        source_external_id="200",
        title="Nvidia launches Blackwell server",
        story_url="https://example.com/story-2",
    )
    reconcile_news_item_relation(db_session, news_item_id=representative.id)

    related = _news_item(
        db_session,
        ingest_key="related-secondary",
        source_external_id="201",
        title="Blackwell server launch details",
        story_url="https://example.com/story-3",
    )
    related.article_domain = "example.com"
    reconcile_news_item_relation(db_session, news_item_id=related.id)
    db_session.commit()

    db_session.refresh(related)
    assert related.representative_news_item_id == representative.id


def test_reconcile_news_item_relation_uses_multiview_primary_score(
    db_session,
    monkeypatch,
) -> None:
    def fake_encode(texts: list[str]) -> np.ndarray:
        first = texts[0]
        if first.startswith("Title: "):
            return np.array(
                [
                    [1.0, 0.0],
                    [0.88, 0.48],
                ],
                dtype=float,
            )
        if first.startswith("Key points:"):
            return np.array(
                [
                    [1.0, 0.0],
                    [0.84, 0.54],
                ],
                dtype=float,
            )
        if first.startswith("Domain: "):
            return np.array(
                [
                    [1.0, 0.0],
                    [0.74, 0.67],
                ],
                dtype=float,
            )
        raise AssertionError(f"Unexpected texts: {texts}")

    monkeypatch.setattr("app.services.news_relations.encode_news_texts", fake_encode)

    representative = _news_item(
        db_session,
        ingest_key="rep-primary",
        source_external_id="300",
        title="OpenAI ships new coding agent",
        story_url="https://example.com/story-300",
    )
    representative.summary_key_points = ["Launches a coding agent", "Targets code review"]
    representative.summary_text = "OpenAI launched a coding agent for code review."
    reconcile_news_item_relation(db_session, news_item_id=representative.id)

    related = _news_item(
        db_session,
        ingest_key="related-primary",
        source_external_id="301",
        title="Coding agent launch expands to code review",
        story_url="https://example.com/story-301",
    )
    related.article_domain = "techmeme.com"
    related.source_label = "Techmeme"
    related.summary_key_points = ["Launches a coding agent", "Targets code review"]
    related.summary_text = "Coverage of the coding agent release for code review workflows."
    reconcile_news_item_relation(db_session, news_item_id=related.id)
    db_session.commit()

    db_session.refresh(related)
    assert related.representative_news_item_id == representative.id


def test_reconcile_news_item_relation_rejects_topical_neighbor_under_multiview_scoring(
    db_session,
    monkeypatch,
) -> None:
    def fake_encode(texts: list[str]) -> np.ndarray:
        first = texts[0]
        if first.startswith("Title: "):
            return np.array(
                [
                    [1.0, 0.0],
                    [0.79, 0.61],
                ],
                dtype=float,
            )
        if first.startswith("Key points:"):
            return np.array(
                [
                    [1.0, 0.0],
                    [0.32, 0.95],
                ],
                dtype=float,
            )
        if first.startswith("Domain: "):
            return np.array(
                [
                    [1.0, 0.0],
                    [0.58, 0.81],
                ],
                dtype=float,
            )
        raise AssertionError(f"Unexpected texts: {texts}")

    monkeypatch.setattr("app.services.news_relations.encode_news_texts", fake_encode)

    representative = _news_item(
        db_session,
        ingest_key="rep-negative",
        source_external_id="400",
        title="OpenAI launches Codex plugin for Claude Code",
        story_url="https://example.com/story-400",
    )
    representative.article_domain = "x.com"
    representative.source_label = "X Following"
    representative.summary_key_points = ["Codex plugin launches for Claude Code"]
    representative.summary_text = "OpenAI launched a Codex plugin inside Claude Code."
    reconcile_news_item_relation(db_session, news_item_id=representative.id)

    adjacent = _news_item(
        db_session,
        ingest_key="adjacent-negative",
        source_external_id="401",
        title="Analytics dashboard launches for Claude Code teams",
        story_url="https://example.com/story-401",
    )
    adjacent.article_domain = "github.com"
    adjacent.source_label = "Show HN"
    adjacent.summary_key_points = ["Dashboard product for Claude Code teams"]
    adjacent.summary_text = "A separate analytics dashboard for Claude Code engineering teams."
    reconcile_news_item_relation(db_session, news_item_id=adjacent.id)
    db_session.commit()

    db_session.refresh(adjacent)
    assert adjacent.representative_news_item_id is None


def test_reconcile_news_item_relation_skips_embeddings_without_title_overlap(
    db_session,
    monkeypatch,
) -> None:
    calls: list[list[str]] = []

    def fake_encode(texts: list[str]) -> np.ndarray:
        calls.append(texts)
        return np.eye(len(texts), dtype=float)

    monkeypatch.setattr("app.services.news_relations.encode_news_texts", fake_encode)

    _news_item(
        db_session,
        ingest_key="rep-unrelated",
        source_external_id="500",
        title="OpenAI ships new coding agent",
        story_url="https://example.com/story-500",
    )
    unrelated = _news_item(
        db_session,
        ingest_key="unrelated",
        source_external_id="501",
        title="Mediterranean cooking guide for spring dinners",
        story_url="https://example.com/story-501",
    )

    reconcile_news_item_relation(db_session, news_item_id=unrelated.id)
    db_session.commit()

    db_session.refresh(unrelated)
    assert unrelated.representative_news_item_id is None
    assert calls == []


def test_reconcile_news_item_relation_caps_semantic_prefilter_candidates(
    db_session,
    monkeypatch,
) -> None:
    call_lengths: list[int] = []

    def fake_encode(texts: list[str]) -> np.ndarray:
        call_lengths.append(len(texts))
        return np.eye(len(texts), dtype=float)

    monkeypatch.setattr("app.services.news_relations.encode_news_texts", fake_encode)

    for index in range(20):
        _news_item(
            db_session,
            ingest_key=f"rep-cap-{index}",
            source_external_id=f"6{index:02d}",
            title=f"OpenAI coding agent launch report {index}",
            story_url=f"https://example.com/story-cap-{index}",
        )

    related = _news_item(
        db_session,
        ingest_key="related-cap",
        source_external_id="699",
        title="OpenAI coding agent launch follow-up",
        story_url="https://example.com/story-cap-related",
    )

    reconcile_news_item_relation(db_session, news_item_id=related.id)

    assert call_lengths
    assert max(call_lengths) == SEMANTIC_PREFILTER_MAX_CANDIDATES + 1
