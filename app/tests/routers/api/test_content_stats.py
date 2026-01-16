"""Tests for content stats endpoints."""

from __future__ import annotations

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentStatusEntry
from app.models.user import User


def _add_inbox_status(db_session, user_id: int, content_id: int) -> None:
    db_session.add(
        ContentStatusEntry(
            user_id=user_id,
            content_id=content_id,
            status="inbox",
        )
    )


def test_processing_count_filters_long_form(client, db_session, test_user) -> None:
    other_user = User(
        apple_id="other_apple_id",
        email="other@example.com",
        full_name="Other User",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    pending_article = Content(
        url="https://example.com/article-1",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.PENDING.value,
        content_metadata={},
    )
    processing_podcast = Content(
        url="https://example.com/podcast-1",
        content_type=ContentType.PODCAST.value,
        status=ContentStatus.PROCESSING.value,
        content_metadata={},
    )
    pending_youtube = Content(
        url="https://youtube.com/watch?v=abc123",
        content_type=ContentType.UNKNOWN.value,
        platform="youtube",
        status=ContentStatus.PENDING.value,
        content_metadata={},
    )
    pending_news = Content(
        url="https://example.com/news-1",
        content_type=ContentType.NEWS.value,
        status=ContentStatus.PENDING.value,
        content_metadata={},
    )
    pending_youtube_news = Content(
        url="https://example.com/news-youtube",
        content_type=ContentType.NEWS.value,
        platform="youtube",
        status=ContentStatus.PENDING.value,
        content_metadata={},
    )
    completed_article = Content(
        url="https://example.com/article-2",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )
    pending_article_no_inbox = Content(
        url="https://example.com/article-3",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.PENDING.value,
        content_metadata={},
    )

    db_session.add_all(
        [
            pending_article,
            processing_podcast,
            pending_youtube,
            pending_news,
            pending_youtube_news,
            completed_article,
            pending_article_no_inbox,
        ]
    )
    db_session.commit()
    for content in (
        pending_article,
        processing_podcast,
        pending_youtube,
        pending_news,
        pending_youtube_news,
        completed_article,
        pending_article_no_inbox,
    ):
        db_session.refresh(content)

    _add_inbox_status(db_session, test_user.id, pending_article.id)
    _add_inbox_status(db_session, test_user.id, processing_podcast.id)
    _add_inbox_status(db_session, test_user.id, pending_youtube.id)
    _add_inbox_status(db_session, test_user.id, pending_news.id)
    _add_inbox_status(db_session, test_user.id, pending_youtube_news.id)
    _add_inbox_status(db_session, test_user.id, completed_article.id)
    _add_inbox_status(db_session, other_user.id, pending_article_no_inbox.id)
    db_session.commit()

    response = client.get("/api/content/stats/processing-count")
    assert response.status_code == 200
    payload = response.json()

    assert payload["processing_count"] == 3
