"""Tests for news link to article conversion endpoint."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content


def test_convert_news_link_to_article(client: TestClient, db_session: Session) -> None:
    """Test converting a news link to a full article."""
    # Create a news item with article URL
    news = Content(
        url="https://news.ycombinator.com/item?id=12345",
        content_type=ContentType.NEWS.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "article": {
                "url": "https://example.com/article",
                "title": "Test Article",
                "source_domain": "example.com"
            },
            "summary": {
                "title": "News Summary",
                "overview": "This is a news summary"
            }
        },
    )
    db_session.add(news)
    db_session.commit()
    db_session.refresh(news)

    # Convert to article
    response = client.post(f"/api/content/{news.id}/convert-to-article")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert "new_content_id" in data
    assert data["original_content_id"] == news.id

    # Verify new article was created
    new_article = db_session.query(Content).filter(Content.id == data["new_content_id"]).first()
    assert new_article is not None
    assert new_article.content_type == ContentType.ARTICLE.value
    assert new_article.url == "https://example.com/article"
    assert new_article.status == ContentStatus.PENDING.value


def test_convert_news_link_no_article_url(client: TestClient, db_session: Session) -> None:
    """Test converting news link without article URL fails gracefully."""
    news = Content(
        url="https://news.ycombinator.com/item?id=12345",
        content_type=ContentType.NEWS.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "summary": {
                "title": "News Summary"
            }
        },
    )
    db_session.add(news)
    db_session.commit()
    db_session.refresh(news)

    response = client.post(f"/api/content/{news.id}/convert-to-article")
    assert response.status_code == 400
    assert "no article url" in response.json()["detail"].lower()


def test_convert_non_news_content(client: TestClient, db_session: Session) -> None:
    """Test that converting non-news content fails."""
    article = Content(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)

    response = client.post(f"/api/content/{article.id}/convert-to-article")
    assert response.status_code == 400
    assert "only news" in response.json()["detail"].lower()


def test_convert_already_exists(client: TestClient, db_session: Session) -> None:
    """Test converting when article already exists returns existing ID."""
    article_url = "https://example.com/article"

    # Create existing article
    existing = Content(
        url=article_url,
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
    )
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    # Create news item pointing to same URL
    news = Content(
        url="https://news.ycombinator.com/item?id=12345",
        content_type=ContentType.NEWS.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={
            "article": {"url": article_url}
        },
    )
    db_session.add(news)
    db_session.commit()
    db_session.refresh(news)

    response = client.post(f"/api/content/{news.id}/convert-to-article")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "success"
    assert data["new_content_id"] == existing.id
    assert data["already_exists"] is True
