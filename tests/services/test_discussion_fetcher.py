"""Tests for discussion ingestion service."""

from __future__ import annotations

import pytest

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentDiscussion
from app.services import discussion_fetcher
from app.services.discussion_fetcher import (
    DiscussionFetchError,
    DiscussionPayload,
    _extract_anchor_titles_from_html,
    _extract_links_from_comments,
    _extract_social_comments_from_groups,
    _is_social_url,
    _is_url_like_text,
    fetch_and_store_discussion,
)


class _FakeResponse:
    def __init__(self, *, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return


class _FakeAuthor:
    def __init__(self, name: str) -> None:
        self.name = name


class _FakeComment:
    def __init__(
        self,
        *,
        comment_id: str,
        body: str,
        author: str,
        created_utc: int,
        replies: list[_FakeComment] | None = None,
        body_html: str | None = None,
    ) -> None:
        self.id = comment_id
        self.body = body
        self.body_html = body_html
        self.author = _FakeAuthor(author)
        self.created_utc = created_utc
        self.replies = _FakeCommentForest(replies or [])


class _FakeCommentForest(list):
    def replace_more(self, limit: int = 0) -> None:
        return None


class _FakeSubmission:
    def __init__(self, *, title: str, num_comments: int, comments: list[_FakeComment]) -> None:
        self.title = title
        self.num_comments = num_comments
        self.comment_sort: str | None = None
        self.comments = _FakeCommentForest(comments)


class _FakeRedditClient:
    def __init__(self, submission: _FakeSubmission) -> None:
        self._submission = submission
        self.requested_ids: list[str] = []

    def submission(self, *, id: str):  # noqa: A002 - mimic praw API
        self.requested_ids.append(id)
        return self._submission


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


def test_build_reddit_payload_uses_authenticated_reddit_client(monkeypatch) -> None:
    reply = _FakeComment(
        comment_id="r1",
        body="Reply body",
        author="bob",
        created_utc=1_700_000_001,
        replies=[],
    )
    root = _FakeComment(
        comment_id="c1",
        body="Root body",
        author="alice",
        created_utc=1_700_000_000,
        replies=[reply],
    )
    fake_submission = _FakeSubmission(title="Thread title", num_comments=2, comments=[root])
    fake_client = _FakeRedditClient(fake_submission)

    monkeypatch.setattr(discussion_fetcher, "_get_reddit_client", lambda: fake_client)

    payload = discussion_fetcher._build_reddit_payload(
        "https://reddit.com/r/test/comments/abc123/thread/",
        comment_cap=10,
    )

    assert fake_client.requested_ids == ["abc123"]
    assert payload.status == "completed"
    assert payload.payload["source_url"] == "https://www.reddit.com/r/test/comments/abc123/thread/"
    assert payload.payload["comments"][0]["comment_id"] == "c1"
    assert payload.payload["comments"][1]["parent_id"] == "c1"
    assert payload.payload["stats"]["declared_comment_count"] == 2


def test_build_reddit_payload_marks_http_403_as_non_retryable(monkeypatch) -> None:
    class _ForbiddenResponseError(Exception):
        def __init__(self) -> None:
            self.response = type("Response", (), {"status_code": 403})()
            super().__init__("forbidden")

    class _FailingClient:
        def submission(self, *, id: str):  # noqa: A002 - mimic praw API
            raise _ForbiddenResponseError()

    monkeypatch.setattr(discussion_fetcher, "_get_reddit_client", lambda: _FailingClient())

    with pytest.raises(DiscussionFetchError) as exc:
        discussion_fetcher._build_reddit_payload(
            "https://reddit.com/r/test/comments/abc123/thread/",
            comment_cap=10,
        )

    assert exc.value.retryable is False


def test_fetch_and_store_discussion_propagates_non_retryable_fetch_errors(
    db_session,
    monkeypatch,
) -> None:
    content = _create_news_content(
        db_session,
        metadata={
            "platform": "reddit",
            "discussion_url": "https://reddit.com/r/test/comments/abc123/thread/",
        },
    )

    monkeypatch.setattr(
        discussion_fetcher,
        "_build_reddit_payload",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            DiscussionFetchError("blocked", retryable=False)
        ),
    )

    result = fetch_and_store_discussion(db_session, content.id)

    assert result.success is False
    assert result.retryable is False
    row = (
        db_session.query(ContentDiscussion)
        .filter(ContentDiscussion.content_id == content.id)
        .first()
    )
    assert row is not None
    assert row.status == "failed"


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


# --- Anchor title extraction tests ---


class TestExtractAnchorTitlesFromHtml:
    def test_extracts_meaningful_anchor_text(self) -> None:
        html = '<a href="https://example.com/article">Great Article</a>'
        result = _extract_anchor_titles_from_html(html)
        assert result["https://example.com/article"] == "Great Article"

    def test_skips_trivial_anchor_text(self) -> None:
        html = (
            '<a href="https://example.com/a">here</a> '
            '<a href="https://example.com/b">click here</a> '
            '<a href="https://example.com/c">link</a>'
        )
        result = _extract_anchor_titles_from_html(html)
        assert result == {}

    def test_skips_url_like_anchor_text(self) -> None:
        html = '<a href="https://example.com/page">https://example.com/page</a>'
        result = _extract_anchor_titles_from_html(html)
        assert result == {}

    def test_skips_url_without_scheme(self) -> None:
        html = '<a href="https://example.com/page">example.com/page</a>'
        result = _extract_anchor_titles_from_html(html)
        assert result == {}

    def test_empty_input(self) -> None:
        assert _extract_anchor_titles_from_html("") == {}
        assert _extract_anchor_titles_from_html("plain text, no anchors") == {}

    def test_multiple_links_first_wins(self) -> None:
        html = (
            '<a href="https://example.com">First Title</a> '
            '<a href="https://example.com">Second Title</a>'
        )
        result = _extract_anchor_titles_from_html(html)
        assert result["https://example.com"] == "First Title"

    def test_mixed_trivial_and_meaningful(self) -> None:
        html = (
            '<a href="https://example.com/a">here</a> '
            '<a href="https://example.com/b">Interesting Paper</a>'
        )
        result = _extract_anchor_titles_from_html(html)
        assert "https://example.com/a" not in result
        assert result["https://example.com/b"] == "Interesting Paper"


class TestIsUrlLikeText:
    def test_exact_match(self) -> None:
        assert _is_url_like_text("https://example.com", "https://example.com") is True

    def test_without_scheme(self) -> None:
        assert _is_url_like_text("example.com/page", "https://example.com/page") is True

    def test_without_www(self) -> None:
        assert _is_url_like_text("example.com/page", "https://www.example.com/page") is True

    def test_meaningful_text(self) -> None:
        assert _is_url_like_text("Great Article", "https://example.com") is False

    def test_trailing_slash_ignored(self) -> None:
        assert _is_url_like_text("https://example.com/", "https://example.com") is True


class TestExtractLinksFromCommentsWithTitles:
    def test_includes_title_when_available(self) -> None:
        comments = [
            {
                "comment_id": "c1",
                "text": "Check out https://example.com/article for details",
            }
        ]
        url_titles = {"https://example.com/article": "Detailed Analysis"}
        links = _extract_links_from_comments(comments, url_titles=url_titles)
        assert len(links) == 1
        assert links[0]["title"] == "Detailed Analysis"
        assert links[0]["url"] == "https://example.com/article"

    def test_omits_title_when_not_available(self) -> None:
        comments = [
            {
                "comment_id": "c1",
                "text": "See https://example.com/other",
            }
        ]
        url_titles = {"https://example.com/article": "Detailed Analysis"}
        links = _extract_links_from_comments(comments, url_titles=url_titles)
        assert len(links) == 1
        assert "title" not in links[0]

    def test_backward_compatible_without_url_titles(self) -> None:
        comments = [
            {
                "comment_id": "c1",
                "text": "Visit https://example.com/page",
            }
        ]
        links = _extract_links_from_comments(comments)
        assert len(links) == 1
        assert "title" not in links[0]


class TestRedditPipelineAnchorTitles:
    def test_body_html_titles_flow_through(self, monkeypatch) -> None:
        root = _FakeComment(
            comment_id="c1",
            body="Check https://example.com/paper for the full paper",
            body_html=(
                'Check <a href="https://example.com/paper">Scaling Laws for LLMs</a>'
                " for the full paper"
            ),
            author="alice",
            created_utc=1_700_000_000,
        )
        fake_submission = _FakeSubmission(
            title="Thread",
            num_comments=1,
            comments=[root],
        )
        fake_client = _FakeRedditClient(fake_submission)
        monkeypatch.setattr(discussion_fetcher, "_get_reddit_client", lambda: fake_client)

        payload = discussion_fetcher._build_reddit_payload(
            "https://reddit.com/r/test/comments/abc123/thread/",
            comment_cap=10,
        )

        links = payload.payload["links"]
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com/paper"
        assert links[0]["title"] == "Scaling Laws for LLMs"

    def test_no_body_html_still_works(self, monkeypatch) -> None:
        root = _FakeComment(
            comment_id="c1",
            body="Check https://example.com/page",
            author="alice",
            created_utc=1_700_000_000,
        )
        fake_submission = _FakeSubmission(
            title="Thread",
            num_comments=1,
            comments=[root],
        )
        fake_client = _FakeRedditClient(fake_submission)
        monkeypatch.setattr(discussion_fetcher, "_get_reddit_client", lambda: fake_client)

        payload = discussion_fetcher._build_reddit_payload(
            "https://reddit.com/r/test/comments/abc123/thread/",
            comment_cap=10,
        )

        links = payload.payload["links"]
        assert len(links) == 1
        assert "title" not in links[0]


# --- Social URL detection tests ---


class TestIsSocialUrl:
    def test_x_dot_com(self) -> None:
        assert _is_social_url("https://x.com/user/status/123") is True

    def test_twitter(self) -> None:
        assert _is_social_url("https://twitter.com/user/status/123") is True

    def test_hackernews(self) -> None:
        assert _is_social_url("https://news.ycombinator.com/item?id=123") is True

    def test_reddit(self) -> None:
        assert _is_social_url("https://www.reddit.com/r/test/comments/abc/") is True

    def test_threads(self) -> None:
        assert _is_social_url("https://www.threads.net/@user/post/abc") is True

    def test_bluesky(self) -> None:
        assert _is_social_url("https://bsky.app/profile/user/post/abc") is True

    def test_mastodon(self) -> None:
        assert _is_social_url("https://mastodon.social/@user/123") is True

    def test_linkedin(self) -> None:
        assert _is_social_url("https://www.linkedin.com/posts/user-abc") is True

    def test_non_social_domain(self) -> None:
        assert _is_social_url("https://example.com/article") is False

    def test_non_social_blog(self) -> None:
        assert _is_social_url("https://techcrunch.com/2025/01/story") is False


# --- Techmeme social comment extraction tests ---


class TestExtractSocialCommentsFromGroups:
    def test_extracts_social_links_as_comments(self) -> None:
        groups = [
            {
                "label": "Discussion",
                "items": [
                    {"title": "HN Thread", "url": "https://news.ycombinator.com/item?id=123"},
                    {"title": "Reddit discussion", "url": "https://www.reddit.com/r/tech/comments/abc/thread/"},
                ],
            }
        ]
        comments = _extract_social_comments_from_groups(groups)
        assert len(comments) == 2
        assert comments[0]["author"] == "news.ycombinator.com"
        assert comments[0]["text"] == "HN Thread"
        assert comments[0]["source_url"] == "https://news.ycombinator.com/item?id=123"
        assert comments[1]["author"] == "reddit.com"

    def test_skips_non_social_links(self) -> None:
        groups = [
            {
                "label": "More",
                "items": [
                    {"title": "TechCrunch", "url": "https://techcrunch.com/story"},
                    {"title": "X post", "url": "https://x.com/user/status/456"},
                ],
            }
        ]
        comments = _extract_social_comments_from_groups(groups)
        assert len(comments) == 1
        assert comments[0]["author"] == "x.com"

    def test_deduplicates_urls(self) -> None:
        groups = [
            {
                "label": "Forums",
                "items": [
                    {"title": "HN", "url": "https://news.ycombinator.com/item?id=1"},
                ],
            },
            {
                "label": "Social",
                "items": [
                    {"title": "HN duplicate", "url": "https://news.ycombinator.com/item?id=1"},
                ],
            },
        ]
        comments = _extract_social_comments_from_groups(groups)
        assert len(comments) == 1

    def test_empty_groups(self) -> None:
        assert _extract_social_comments_from_groups([]) == []


# --- Techmeme payload with social comments tests ---


def test_build_techmeme_payload_includes_social_comments(monkeypatch) -> None:
    groups = [
        {
            "label": "Forums",
            "items": [
                {"title": "Hacker News", "url": "https://news.ycombinator.com/item?id=123"},
                {"title": "TechCrunch Article", "url": "https://techcrunch.com/story"},
            ],
        }
    ]

    monkeypatch.setattr(
        discussion_fetcher,
        "_fetch_techmeme_discussion_groups",
        lambda *args, **kwargs: groups,
    )

    payload = discussion_fetcher._build_techmeme_payload(
        "https://www.techmeme.com/260217/p39#a260217p39",
        {"aggregator": {"external_id": "p39#a260217p39"}},
    )

    assert payload.status == "completed"
    assert payload.mode == "discussion_list"
    assert payload.payload["mode"] == "discussion_list"
    # Should have one social comment (HN), not the TechCrunch article
    comments = payload.payload["comments"]
    assert len(comments) == 1
    assert comments[0]["author"] == "news.ycombinator.com"
    assert comments[0]["text"] == "Hacker News"
    # Groups should still be intact
    assert len(payload.payload["discussion_groups"]) == 1


# --- Comment count denormalization tests ---


def test_fetch_and_store_denormalizes_comment_count_for_hn(db_session, monkeypatch) -> None:
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
                "stats": {
                    "cap": 500,
                    "fetched_count": 1,
                    "cap_reached": False,
                    "declared_comment_count": 42,
                },
            },
        ),
    )

    result = fetch_and_store_discussion(db_session, content.id)
    assert result.success is True

    db_session.refresh(content)
    assert content.content_metadata["comment_count"] == 42


def test_fetch_and_store_denormalizes_comment_count_for_techmeme(
    db_session, monkeypatch
) -> None:
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
                    {"title": "HN", "url": "https://news.ycombinator.com/item?id=1"},
                    {"title": "Reddit", "url": "https://www.reddit.com/r/tech/comments/abc/thread/"},
                ],
            }
        ],
    )

    result = fetch_and_store_discussion(db_session, content.id)
    assert result.success is True

    db_session.refresh(content)
    assert content.content_metadata["comment_count"] == 2
    # top_comment should also be set from social comments
    assert content.content_metadata["top_comment"]["author"] == "news.ycombinator.com"
