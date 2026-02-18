"""Tests for discussion ingestion service."""

from __future__ import annotations

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentDiscussion
from app.services import discussion_fetcher
from app.services.discussion_fetcher import DiscussionPayload, fetch_and_store_discussion


class _FakeResponse:
    def __init__(self, *, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return


def _create_news_content(db_session, *, metadata: dict[str, object]) -> Content:
    content = Content(
        content_type=ContentType.NEWS.value,
        url="https://example.com/story",
        title="Example Story",
        source="example.com",
        platform=str(metadata.get("platform") or ""),
        status=ContentStatus.NEW.value,
        content_metadata=metadata,
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def test_fetch_techmeme_discussion_groups_parses_grouped_links(monkeypatch) -> None:
    html = """
    <html>
      <body>
        <div class="item" id="0i1">
          <span pml="260217p39"></span>
          <span class="drhed">More:</span>
          <span class="bls">
            <a href="https://example.com/a">Example A</a>
            <a href="https://example.com/b">Example B</a>
          </span>
          <span class="drhed">Forums:</span>
          <span class="bls">
            <a href="https://news.ycombinator.com/item?id=123">Hacker News</a>
            <a href="https://www.reddit.com/r/test/comments/abc123/thread/">r/test</a>
          </span>
        </div>
      </body>
    </html>
    """

    monkeypatch.setattr(
        discussion_fetcher.httpx,
        "get",
        lambda *args, **kwargs: _FakeResponse(text=html),
    )

    groups = discussion_fetcher._fetch_techmeme_discussion_groups(
        "https://www.techmeme.com/260217/p39#a260217p39",
        {"aggregator": {"external_id": "p39#a260217p39"}},
    )

    assert len(groups) == 2
    assert groups[0]["label"] == "More"
    assert groups[1]["label"] == "Forums"
    forum_urls = [item["url"] for item in groups[1]["items"]]
    assert "https://news.ycombinator.com/item?id=123" in forum_urls
    assert "https://www.reddit.com/r/test/comments/abc123/thread/" in forum_urls


def test_fetch_and_store_discussion_techmeme_persists_list(db_session, monkeypatch) -> None:
    content = _create_news_content(
        db_session,
        metadata={
            "platform": "techmeme",
            "discussion_url": "https://www.techmeme.com/260217/p39#a260217p39",
        },
    )

    monkeypatch.setattr(
        discussion_fetcher,
        "_fetch_techmeme_discussion_groups",
        lambda *args, **kwargs: [
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
    )

    result = fetch_and_store_discussion(db_session, content.id)

    assert result.success is True
    assert result.status == "completed"

    row = (
        db_session.query(ContentDiscussion)
        .filter(ContentDiscussion.content_id == content.id)
        .first()
    )
    assert row is not None
    assert row.status == "completed"
    assert row.discussion_data["mode"] == "discussion_list"
    assert row.discussion_data["discussion_groups"][0]["label"] == "Forums"


def test_fetch_and_store_discussion_hn_persists_comments(db_session, monkeypatch) -> None:
    content = _create_news_content(
        db_session,
        metadata={
            "platform": "hackernews",
            "discussion_url": "https://news.ycombinator.com/item?id=123",
        },
    )

    monkeypatch.setattr(
        discussion_fetcher,
        "_build_hackernews_payload",
        lambda *args, **kwargs: DiscussionPayload(
            status="completed",
            mode="comments",
            payload={
                "mode": "comments",
                "source_url": "https://news.ycombinator.com/item?id=123",
                "discussion_groups": [],
                "comments": [
                    {
                        "comment_id": "c1",
                        "parent_id": None,
                        "author": "alice",
                        "text": "Great post",
                        "compact_text": "Great post",
                        "depth": 0,
                        "created_at": None,
                        "source_url": "https://news.ycombinator.com/item?id=123",
                    }
                ],
                "compact_comments": ["Great post"],
                "links": [],
                "stats": {"cap": 500, "fetched_count": 1, "cap_reached": False},
            },
        ),
    )

    result = fetch_and_store_discussion(db_session, content.id)

    assert result.success is True
    assert result.status == "completed"

    row = (
        db_session.query(ContentDiscussion)
        .filter(ContentDiscussion.content_id == content.id)
        .first()
    )
    assert row is not None
    assert row.discussion_data["mode"] == "comments"
    assert row.discussion_data["comments"][0]["author"] == "alice"


def test_fetch_and_store_discussion_unsupported_platform_is_partial(db_session) -> None:
    content = _create_news_content(
        db_session,
        metadata={
            "platform": "unknown_platform",
            "discussion_url": "https://example.com/discussion",
        },
    )

    result = fetch_and_store_discussion(db_session, content.id)

    assert result.success is True
    assert result.status == "partial"

    row = (
        db_session.query(ContentDiscussion)
        .filter(ContentDiscussion.content_id == content.id)
        .first()
    )
    assert row is not None
    assert row.status == "partial"
    assert row.discussion_data["mode"] == "none"
