"""Tests for content discussion API endpoint."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import ContentDiscussion


def test_get_content_discussion_returns_not_ready_when_missing(
    client,
    content_factory,
    status_entry_factory,
    test_user,
) -> None:
    content = content_factory(
        content_type=ContentType.NEWS.value,
        url="https://example.com/story",
        title="Example",
        source="example.com",
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "platform": "hackernews",
            "discussion_url": "https://news.ycombinator.com/item?id=123",
        },
    )
    status_entry_factory(user=test_user, content=content, status="inbox")

    response = client.get(f"/api/content/{content.id}/discussion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_ready"
    assert payload["mode"] == "none"
    assert payload["discussion_url"] == "https://news.ycombinator.com/item?id=123"


def test_get_content_discussion_returns_comments_payload(
    client,
    content_factory,
    db_session,
    discussion_payload_factory,
    status_entry_factory,
    test_user,
) -> None:
    content = content_factory(
        content_type=ContentType.NEWS.value,
        url="https://example.com/story",
        title="Example",
        source="example.com",
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "platform": "hackernews",
            "discussion_url": "https://news.ycombinator.com/item?id=123",
        },
    )
    status_entry_factory(user=test_user, content=content, status="inbox")
    db_session.add(
        ContentDiscussion(
            content_id=content.id,
            platform="hackernews",
            status="completed",
            discussion_data=discussion_payload_factory(
                discussion_url="https://news.ycombinator.com/item?id=123",
            ),
        )
    )
    db_session.commit()

    response = client.get(f"/api/content/{content.id}/discussion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["mode"] == "comments"
    assert payload["comments"][0]["author"] == "alice"
    assert payload["links"][0]["url"] == "https://example.com"


def test_get_content_discussion_returns_discussion_list_payload(
    client,
    content_factory,
    db_session,
    discussion_payload_factory,
    status_entry_factory,
    test_user,
) -> None:
    content = content_factory(
        content_type=ContentType.NEWS.value,
        url="https://example.com/story",
        title="Example",
        source="example.com",
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "platform": "techmeme",
            "discussion_url": "https://www.techmeme.com/260217/p39#a260217p39",
        },
    )
    status_entry_factory(user=test_user, content=content, status="inbox")
    db_session.add(
        ContentDiscussion(
            content_id=content.id,
            platform="techmeme",
            status="completed",
            discussion_data=discussion_payload_factory(
                discussion_url="https://www.techmeme.com/260217/p39#a260217p39",
                mode="discussion_list",
            ),
        )
    )
    db_session.commit()

    response = client.get(f"/api/content/{content.id}/discussion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "discussion_list"
    assert payload["discussion_groups"][0]["label"] == "Forums"
    assert payload["discussion_groups"][0]["items"][0]["title"] == "Hacker News"


def test_get_content_discussion_returns_404_when_missing_content(client) -> None:
    response = client.get("/api/content/999999/discussion")
    assert response.status_code == 404


def test_get_news_item_discussion_returns_comments_payload_from_legacy_content(
    client,
    content_factory,
    db_session,
    discussion_payload_factory,
    news_item_factory,
    test_user,
) -> None:
    content = content_factory(
        content_type=ContentType.NEWS.value,
        url="https://example.com/story",
        title="Example",
        source="example.com",
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "platform": "hackernews",
            "discussion_url": "https://news.ycombinator.com/item?id=456",
        },
    )
    news_item = news_item_factory(
        ingest_key="hn-456",
        platform="hackernews",
        canonical_item_url="https://example.com/story",
        discussion_url="https://news.ycombinator.com/item?id=456",
        raw_metadata={},
        status="ready",
        legacy_content_id=content.id,
    )
    db_session.add(
        ContentDiscussion(
            content_id=content.id,
            platform="hackernews",
            status="completed",
            discussion_data=discussion_payload_factory(
                discussion_url="https://news.ycombinator.com/item?id=456",
            ),
        )
    )
    db_session.commit()

    response = client.get(f"/api/news/items/{news_item.id}/discussion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["mode"] == "comments"
    assert payload["discussion_url"] == "https://news.ycombinator.com/item?id=456"
    assert payload["comments"][0]["author"] == "alice"


def test_get_news_item_discussion_returns_embedded_payload_without_legacy_content(
    client,
    discussion_payload_factory,
    news_item_factory,
) -> None:
    news_item = news_item_factory(
        ingest_key="hn-embedded-discussion",
        platform="hackernews",
        source_type="hackernews",
        source_label="Hacker News",
        source_external_id="hn-embedded-discussion",
        canonical_item_url="https://news.ycombinator.com/item?id=789",
        canonical_story_url="https://example.com/story",
        article_url="https://example.com/story",
        article_title="Embedded discussion story",
        article_domain="example.com",
        discussion_url="https://news.ycombinator.com/item?id=789",
        summary_title="Embedded discussion story",
        summary_key_points=["Point one"],
        summary_text="Short summary",
        raw_metadata={
            "discussion_url": "https://news.ycombinator.com/item?id=789",
            "discussion_status": "completed",
            "discussion_fetched_at": "2026-04-04T12:00:00+00:00",
            "discussion_payload": discussion_payload_factory(
                discussion_url="https://news.ycombinator.com/item?id=789",
                comments=[
                    {
                        "comment_id": "c-embedded",
                        "author": "alice",
                        "text": "Embedded comment",
                        "compact_text": "Embedded comment",
                        "depth": 0,
                    }
                ],
                links=[{"url": "https://example.com/comment-link", "source": "comment"}],
                stats={"fetched_count": 1},
            ),
        },
        status="ready",
        published_at=datetime.now(UTC).replace(tzinfo=None),
        ingested_at=datetime.now(UTC).replace(tzinfo=None),
        processed_at=datetime.now(UTC).replace(tzinfo=None),
    )

    response = client.get(f"/api/news/items/{news_item.id}/discussion")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["mode"] == "comments"
    assert payload["discussion_url"] == "https://news.ycombinator.com/item?id=789"
    assert payload["fetched_at"] == "2026-04-04T12:00:00+00:00"
    assert payload["comments"][0]["author"] == "alice"
    assert payload["comments"][0]["text"] == "Embedded comment"
    assert payload["links"][0]["url"] == "https://example.com/comment-link"
