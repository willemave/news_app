"""Tests for content stats endpoints."""

from __future__ import annotations

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentFavorites, ContentReadStatus, ContentStatusEntry
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


def test_long_form_stats_counts(client, db_session, test_user) -> None:
    other_user = User(
        apple_id="other_user_apple_id",
        email="other@example.com",
        full_name="Other User",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    completed_article_unread = Content(
        url="https://example.com/article-unread",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )
    completed_podcast_read = Content(
        url="https://example.com/podcast-read",
        content_type=ContentType.PODCAST.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )
    completed_article_favorited = Content(
        url="https://example.com/article-favorite",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )
    completed_youtube = Content(
        url="https://youtube.com/watch?v=xyz",
        content_type=ContentType.UNKNOWN.value,
        platform="youtube",
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )
    completed_news = Content(
        url="https://example.com/news",
        content_type=ContentType.NEWS.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )
    processing_article = Content(
        url="https://example.com/article-processing",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.PROCESSING.value,
        content_metadata={},
    )
    pending_podcast = Content(
        url="https://example.com/podcast-pending",
        content_type=ContentType.PODCAST.value,
        status=ContentStatus.PENDING.value,
        content_metadata={},
    )
    completed_other_user = Content(
        url="https://example.com/article-other",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )

    db_session.add_all(
        [
            completed_article_unread,
            completed_podcast_read,
            completed_article_favorited,
            completed_youtube,
            completed_news,
            processing_article,
            pending_podcast,
            completed_other_user,
        ]
    )
    db_session.commit()
    for content in (
        completed_article_unread,
        completed_podcast_read,
        completed_article_favorited,
        completed_youtube,
        completed_news,
        processing_article,
        pending_podcast,
        completed_other_user,
    ):
        db_session.refresh(content)

    _add_inbox_status(db_session, test_user.id, completed_article_unread.id)
    _add_inbox_status(db_session, test_user.id, completed_podcast_read.id)
    _add_inbox_status(db_session, test_user.id, completed_article_favorited.id)
    _add_inbox_status(db_session, test_user.id, completed_youtube.id)
    _add_inbox_status(db_session, test_user.id, completed_news.id)
    _add_inbox_status(db_session, test_user.id, processing_article.id)
    _add_inbox_status(db_session, test_user.id, pending_podcast.id)
    _add_inbox_status(db_session, other_user.id, completed_other_user.id)
    db_session.commit()

    db_session.add(
        ContentReadStatus(
            user_id=test_user.id,
            content_id=completed_podcast_read.id,
        )
    )
    db_session.add(
        ContentFavorites(
            user_id=test_user.id,
            content_id=completed_article_favorited.id,
        )
    )
    db_session.commit()

    response = client.get("/api/content/stats/long-form")
    assert response.status_code == 200
    payload = response.json()

    assert payload["total_count"] == 4
    assert payload["read_count"] == 1
    assert payload["unread_count"] == 3
    assert payload["favorited_count"] == 1
    assert payload["processing_count"] == 2
