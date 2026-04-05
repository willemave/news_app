"""Tests for content discussion API endpoint."""

from __future__ import annotations

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import ContentDiscussion, NewsItem


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
            discussion_data={
                "mode": "comments",
                "source_url": "https://news.ycombinator.com/item?id=123",
                "comments": [
                    {
                        "comment_id": "c1",
                        "author": "alice",
                        "text": "great",
                        "compact_text": "great",
                        "depth": 0,
                    }
                ],
                "discussion_groups": [],
                "links": [{"url": "https://example.com", "source": "comment"}],
                "stats": {"fetched_count": 1},
            },
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
            discussion_data={
                "mode": "discussion_list",
                "source_url": "https://www.techmeme.com/260217/p39#a260217p39",
                "discussion_groups": [
                    {
                        "label": "Forums",
                        "items": [
                            {
                                "title": "Hacker News",
                                "url": "https://news.ycombinator.com/item?id=123",
                            }
                        ],
                    }
                ],
                "comments": [],
                "links": [
                    {
                        "url": "https://news.ycombinator.com/item?id=123",
                        "source": "discussion_group",
                        "group_label": "Forums",
                    }
                ],
                "stats": {"group_count": 1},
            },
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
    news_item = NewsItem(
        ingest_key="hn-456",
        visibility_scope="global",
        platform="hackernews",
        canonical_item_url="https://example.com/story",
        discussion_url="https://news.ycombinator.com/item?id=456",
        raw_metadata={},
        status="ready",
        legacy_content_id=content.id,
    )
    db_session.add(news_item)
    db_session.flush()
    db_session.add(
        ContentDiscussion(
            content_id=content.id,
            platform="hackernews",
            status="completed",
            discussion_data={
                "mode": "comments",
                "source_url": "https://news.ycombinator.com/item?id=456",
                "comments": [
                    {
                        "comment_id": "c1",
                        "author": "alice",
                        "text": "great",
                        "compact_text": "great",
                        "depth": 0,
                    }
                ],
                "discussion_groups": [],
                "links": [{"url": "https://example.com", "source": "comment"}],
                "stats": {"fetched_count": 1},
            },
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
