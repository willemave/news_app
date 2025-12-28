"""Tests for tweet suggestions API endpoint."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content
from app.services.tweet_suggestions import (
    TWEET_MODEL,
    TweetSuggestionData,
    TweetSuggestionsResult,
)


def test_tweet_suggestions_success(client: TestClient, db_session: Session) -> None:
    """Test successful tweet suggestion generation."""
    # Create completed article - use empty bullet_points to avoid validation complexity
    # The endpoint mocks the tweet generation anyway
    article = Content(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        title="Test Article",
        source="Tech Blog",
        content_metadata={
            "source": "Tech Blog",
            "summary": {
                "title": "Great Article",
                "overview": (
                    "This is an overview that is long enough to pass validation "
                    "requirements for the structured summary."
                ),
                "bullet_points": [],
            },
        },
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)

    # Mock the tweet generation service
    mock_result = TweetSuggestionsResult(
        content_id=article.id,
        creativity=5,
        length="medium",
        model=TWEET_MODEL,
        suggestions=[
            TweetSuggestionData(id=1, text="Tweet 1", style_label="insightful"),
            TweetSuggestionData(id=2, text="Tweet 2", style_label="provocative"),
            TweetSuggestionData(id=3, text="Tweet 3", style_label="reflective"),
        ],
    )

    with patch(
        "app.routers.api.content_actions.generate_tweet_suggestions",
        return_value=mock_result,
    ):
        response = client.post(
            f"/api/content/{article.id}/tweet-suggestions",
            json={"creativity": 5},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content_id"] == article.id
    assert data["creativity"] == 5
    assert data["model"] == TWEET_MODEL
    assert len(data["suggestions"]) == 3
    assert data["suggestions"][0]["text"] == "Tweet 1"
    assert data["suggestions"][0]["style_label"] == "insightful"


def test_tweet_suggestions_with_message(client: TestClient, db_session: Session) -> None:
    """Test tweet generation with user message/guidance."""
    article = Content(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        title="Test Article",
        content_metadata={
            "summary": {
                "title": "Article Title",
                "overview": "Overview",
                "bullet_points": [],
            },
        },
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)

    mock_result = TweetSuggestionsResult(
        content_id=article.id,
        creativity=7,
        length="medium",
        model=TWEET_MODEL,
        suggestions=[
            TweetSuggestionData(id=1, text="Startup focused tweet", style_label="a"),
            TweetSuggestionData(id=2, text="Another startup tweet", style_label="b"),
            TweetSuggestionData(id=3, text="Third startup tweet", style_label="c"),
        ],
    )

    with patch(
        "app.routers.api.content_actions.generate_tweet_suggestions",
        return_value=mock_result,
    ) as mock_gen:
        response = client.post(
            f"/api/content/{article.id}/tweet-suggestions",
            json={
                "message": "focus on startup implications",
                "creativity": 7,
            },
        )

        # Verify the message was passed to the service
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["message"] == "focus on startup implications"
        assert call_kwargs["creativity"] == 7

    assert response.status_code == 200


def test_tweet_suggestions_content_not_found(client: TestClient, db_session: Session) -> None:
    """Test 404 for non-existent content."""
    response = client.post(
        "/api/content/99999/tweet-suggestions",
        json={"creativity": 5},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_tweet_suggestions_content_not_completed(client: TestClient, db_session: Session) -> None:
    """Test 400 for content that's not completed."""
    # Create content with NEW status
    article = Content(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.NEW.value,  # Not completed
        title="Test Article",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)

    response = client.post(
        f"/api/content/{article.id}/tweet-suggestions",
        json={"creativity": 5},
    )

    assert response.status_code == 400
    assert "not ready" in response.json()["detail"].lower()


def test_tweet_suggestions_podcast_supported(client: TestClient, db_session: Session) -> None:
    """Podcasts are now supported for tweet generation."""
    podcast = Content(
        url="https://example.com/podcast",
        content_type=ContentType.PODCAST.value,
        status=ContentStatus.COMPLETED.value,
        title="Test Podcast",
        content_metadata={
            "summary": {
                "title": "Podcast Episode",
                "overview": "Summary of the podcast episode.",
                "bullet_points": [],
            }
        },
    )
    db_session.add(podcast)
    db_session.commit()
    db_session.refresh(podcast)

    mock_result = TweetSuggestionsResult(
        content_id=podcast.id,
        creativity=5,
        length="medium",
        model=TWEET_MODEL,
        suggestions=[
            TweetSuggestionData(id=1, text="Podcast tweet 1", style_label="a"),
            TweetSuggestionData(id=2, text="Podcast tweet 2", style_label="b"),
            TweetSuggestionData(id=3, text="Podcast tweet 3", style_label="c"),
        ],
    )

    with patch(
        "app.routers.api.content_actions.generate_tweet_suggestions",
        return_value=mock_result,
    ):
        response = client.post(
            f"/api/content/{podcast.id}/tweet-suggestions",
            json={"creativity": 5},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content_id"] == podcast.id


def test_tweet_suggestions_creativity_out_of_range(client: TestClient, db_session: Session) -> None:
    """Test 422 for creativity values outside valid range."""
    article = Content(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        title="Test Article",
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)

    # Test creativity too low
    response = client.post(
        f"/api/content/{article.id}/tweet-suggestions",
        json={"creativity": 0},  # Below minimum (1)
    )
    assert response.status_code == 422

    # Test creativity too high
    response = client.post(
        f"/api/content/{article.id}/tweet-suggestions",
        json={"creativity": 15},  # Above maximum (10)
    )
    assert response.status_code == 422


def test_tweet_suggestions_llm_failure(client: TestClient, db_session: Session) -> None:
    """Test 502 when LLM generation fails."""
    article = Content(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        title="Test Article",
        content_metadata={
            "summary": {
                "title": "Article Title",
                "overview": "Overview",
                "bullet_points": [],
            },
        },
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)

    # Mock service to return None (failure)
    with patch(
        "app.routers.api.content_actions.generate_tweet_suggestions",
        return_value=None,
    ):
        response = client.post(
            f"/api/content/{article.id}/tweet-suggestions",
            json={"creativity": 5},
        )

    assert response.status_code == 502
    assert "failed" in response.json()["detail"].lower()


def test_tweet_suggestions_news_content(client: TestClient, db_session: Session) -> None:
    """Test tweet generation works for news content type."""
    news = Content(
        url="https://news.ycombinator.com/item?id=12345",
        content_type=ContentType.NEWS.value,
        status=ContentStatus.COMPLETED.value,
        title="HN Discussion",
        content_metadata={
            "article": {
                "url": "https://example.com/article",
                "title": "The Article",
            },
            "summary": {
                "title": "News Summary",
                "overview": "Overview of the news",
                "bullet_points": ["Point 1"],
            },
        },
    )
    db_session.add(news)
    db_session.commit()
    db_session.refresh(news)

    mock_result = TweetSuggestionsResult(
        content_id=news.id,
        creativity=5,
        length="medium",
        model=TWEET_MODEL,
        suggestions=[
            TweetSuggestionData(id=1, text="News tweet 1", style_label="a"),
            TweetSuggestionData(id=2, text="News tweet 2", style_label="b"),
            TweetSuggestionData(id=3, text="News tweet 3", style_label="c"),
        ],
    )

    with patch(
        "app.routers.api.content_actions.generate_tweet_suggestions",
        return_value=mock_result,
    ):
        response = client.post(
            f"/api/content/{news.id}/tweet-suggestions",
            json={"creativity": 5},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["content_id"] == news.id


def test_tweet_suggestions_default_creativity(client: TestClient, db_session: Session) -> None:
    """Test that default creativity (5) is used when not provided."""
    article = Content(
        url="https://example.com/article",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        title="Test Article",
        content_metadata={
            "summary": {
                "title": "Article Title",
                "overview": "Overview",
                "bullet_points": [],
            },
        },
    )
    db_session.add(article)
    db_session.commit()
    db_session.refresh(article)

    mock_result = TweetSuggestionsResult(
        content_id=article.id,
        creativity=5,  # Default
        length="medium",
        model=TWEET_MODEL,
        suggestions=[
            TweetSuggestionData(id=1, text="Tweet 1", style_label="a"),
            TweetSuggestionData(id=2, text="Tweet 2", style_label="b"),
            TweetSuggestionData(id=3, text="Tweet 3", style_label="c"),
        ],
    )

    with patch(
        "app.routers.api.content_actions.generate_tweet_suggestions",
        return_value=mock_result,
    ) as mock_gen:
        response = client.post(
            f"/api/content/{article.id}/tweet-suggestions",
            json={},  # No creativity specified
        )

        # Verify default creativity was used
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["creativity"] == 5

    assert response.status_code == 200
