"""Tests for can_subscribe behavior in content detail response."""

from app.constants import SELF_SUBMISSION_SOURCE
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.services.scraper_configs import CreateUserScraperConfig, create_user_scraper_config


def _create_content(db_session, *, content_type: str, source: str, metadata: dict) -> Content:
    content = Content(
        url="https://example.com/article",
        content_type=content_type,
        title="Example",
        source=source,
        status=ContentStatus.COMPLETED.value,
        content_metadata=metadata,
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def test_can_subscribe_self_submission_true_when_missing_config(client, db_session, test_user):
    metadata = {
        "source": SELF_SUBMISSION_SOURCE,
        "content_type": "html",
        "content": "Test",
        "detected_feed": {
            "url": "https://example.com/feed",
            "type": "atom",
            "title": "Example Feed",
            "format": "rss",
        },
    }
    content = _create_content(
        db_session,
        content_type=ContentType.ARTICLE.value,
        source=SELF_SUBMISSION_SOURCE,
        metadata=metadata,
    )

    response = client.get(f"/api/content/{content.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["can_subscribe"] is True


def test_can_subscribe_false_when_already_subscribed(client, db_session, test_user):
    payload = CreateUserScraperConfig(
        scraper_type="atom",
        display_name="Example Feed",
        config={"feed_url": "https://example.com/feed"},
        is_active=True,
    )
    create_user_scraper_config(db_session, test_user.id, payload)

    metadata = {
        "source": SELF_SUBMISSION_SOURCE,
        "content_type": "html",
        "content": "Test",
        "detected_feed": {
            "url": "https://example.com/feed",
            "type": "atom",
            "title": "Example Feed",
            "format": "rss",
        },
    }
    content = _create_content(
        db_session,
        content_type=ContentType.ARTICLE.value,
        source=SELF_SUBMISSION_SOURCE,
        metadata=metadata,
    )

    response = client.get(f"/api/content/{content.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["can_subscribe"] is False


def test_can_subscribe_false_for_non_news_non_self_submission(client, db_session, test_user):
    metadata = {
        "source": "web",
        "content_type": "html",
        "content": "Test",
        "detected_feed": {
            "url": "https://example.com/feed",
            "type": "atom",
            "title": "Example Feed",
            "format": "rss",
        },
    }
    content = _create_content(
        db_session,
        content_type=ContentType.ARTICLE.value,
        source="web",
        metadata=metadata,
    )

    response = client.get(f"/api/content/{content.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["can_subscribe"] is False


def test_can_subscribe_true_for_news_content(client, db_session, test_user):
    metadata = {
        "source": "hackernews",
        "platform": "hackernews",
        "article": {
            "url": "https://example.com/story",
            "title": "Example Story",
            "source_domain": "example.com",
        },
        "detected_feed": {
            "url": "https://example.com/feed",
            "type": "atom",
            "title": "Example Feed",
            "format": "rss",
        },
    }
    content = _create_content(
        db_session,
        content_type=ContentType.NEWS.value,
        source="hackernews",
        metadata=metadata,
    )

    response = client.get(f"/api/content/{content.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["can_subscribe"] is True
