from __future__ import annotations

from datetime import UTC, datetime

from app.constants import DEFAULT_NEW_FEED_LIMIT
from app.models.schema import Content, FeedDiscoveryRun, FeedDiscoverySuggestion, UserScraperConfig


def _create_run(db_session, user_id: int) -> FeedDiscoveryRun:
    run = FeedDiscoveryRun(
        user_id=user_id,
        status="completed",
        direction_summary="Test summary",
        seed_content_ids=[],
        created_at=datetime.now(UTC),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def test_get_discovery_suggestions_grouped(client, db_session, test_user):
    run = _create_run(db_session, test_user.id)
    suggestions = [
        FeedDiscoverySuggestion(
            run_id=run.id,
            user_id=test_user.id,
            suggestion_type="atom",
            site_url="https://example.com",
            feed_url="https://example.com/feed.xml",
            title="Example Feed",
            status="new",
            config={"feed_url": "https://example.com/feed.xml"},
        ),
        FeedDiscoverySuggestion(
            run_id=run.id,
            user_id=test_user.id,
            suggestion_type="podcast_rss",
            site_url="https://pod.example.com",
            feed_url="https://pod.example.com/rss.xml",
            title="Example Podcast",
            status="new",
            config={"feed_url": "https://pod.example.com/rss.xml"},
        ),
        FeedDiscoverySuggestion(
            run_id=run.id,
            user_id=test_user.id,
            suggestion_type="youtube",
            site_url="https://www.youtube.com/channel/UC123",
            feed_url="https://www.youtube.com/channel/UC123",
            title="Example YouTube",
            status="new",
            config={"feed_url": "https://www.youtube.com/channel/UC123", "channel_id": "UC123"},
        ),
    ]
    db_session.add_all(suggestions)
    db_session.commit()

    response = client.get("/api/discovery/suggestions")
    assert response.status_code == 200
    data = response.json()
    assert len(data["feeds"]) == 1
    assert len(data["podcasts"]) == 1
    assert len(data["youtube"]) == 1


def test_discovery_subscribe_creates_config(client, db_session, test_user):
    run = _create_run(db_session, test_user.id)
    suggestion = FeedDiscoverySuggestion(
        run_id=run.id,
        user_id=test_user.id,
        suggestion_type="substack",
        site_url="https://example.substack.com",
        feed_url="https://example.substack.com/feed",
        title="Example Substack",
        status="new",
        config={"feed_url": "https://example.substack.com/feed"},
    )
    db_session.add(suggestion)
    db_session.commit()
    db_session.refresh(suggestion)

    response = client.post(
        "/api/discovery/subscribe",
        json={"suggestion_ids": [suggestion.id]},
    )
    assert response.status_code == 200
    data = response.json()
    assert suggestion.id in data["subscribed"]

    config = (
        db_session.query(UserScraperConfig)
        .filter(UserScraperConfig.user_id == test_user.id)
        .first()
    )
    assert config is not None
    assert config.feed_url == "https://example.substack.com/feed"
    assert config.config.get("limit") == DEFAULT_NEW_FEED_LIMIT


def test_discovery_subscribe_uses_feed_url_when_missing_in_config(
    client,
    db_session,
    test_user,
):
    run = _create_run(db_session, test_user.id)
    suggestion = FeedDiscoverySuggestion(
        run_id=run.id,
        user_id=test_user.id,
        suggestion_type="podcast_rss",
        site_url="https://podcasts.apple.com/us/podcast/example/id123",
        feed_url="https://example.com/podcast/rss.xml",
        title="Example Podcast",
        status="new",
        config={"source": "apple_podcasts", "podcast_id": "123"},
    )
    db_session.add(suggestion)
    db_session.commit()
    db_session.refresh(suggestion)

    response = client.post(
        "/api/discovery/subscribe",
        json={"suggestion_ids": [suggestion.id]},
    )
    assert response.status_code == 200
    data = response.json()
    assert suggestion.id in data["subscribed"]

    config = (
        db_session.query(UserScraperConfig)
        .filter(UserScraperConfig.user_id == test_user.id)
        .first()
    )
    assert config is not None
    assert config.feed_url == "https://example.com/podcast/rss.xml"
    assert config.config.get("limit") == DEFAULT_NEW_FEED_LIMIT


def test_discovery_dismiss_marks_suggestion(client, db_session, test_user):
    run = _create_run(db_session, test_user.id)
    suggestion = FeedDiscoverySuggestion(
        run_id=run.id,
        user_id=test_user.id,
        suggestion_type="atom",
        site_url="https://example.com",
        feed_url="https://example.com/feed.xml",
        title="Example Feed",
        status="new",
        config={"feed_url": "https://example.com/feed.xml"},
    )
    db_session.add(suggestion)
    db_session.commit()
    db_session.refresh(suggestion)

    response = client.post(
        "/api/discovery/dismiss",
        json={"suggestion_ids": [suggestion.id]},
    )
    assert response.status_code == 200

    db_session.refresh(suggestion)
    assert suggestion.status == "dismissed"


def test_discovery_add_item_creates_content(client, db_session, test_user):
    run = _create_run(db_session, test_user.id)
    suggestion = FeedDiscoverySuggestion(
        run_id=run.id,
        user_id=test_user.id,
        suggestion_type="podcast_rss",
        site_url="https://example.com",
        feed_url="https://example.com/feed.xml",
        item_url="https://example.com/episode-1",
        title="Example Episode",
        status="new",
        config={"feed_url": "https://example.com/feed.xml"},
    )
    db_session.add(suggestion)
    db_session.commit()
    db_session.refresh(suggestion)

    response = client.post(
        "/api/discovery/add-item",
        json={"suggestion_ids": [suggestion.id]},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["created"]) == 1

    content = db_session.query(Content).filter(Content.url == suggestion.item_url).first()
    assert content is not None


def test_discovery_history_groups_runs(client, db_session, test_user):
    older_run = FeedDiscoveryRun(
        user_id=test_user.id,
        status="completed",
        direction_summary="Older summary",
        seed_content_ids=[],
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer_run = FeedDiscoveryRun(
        user_id=test_user.id,
        status="completed",
        direction_summary="Newer summary",
        seed_content_ids=[],
        created_at=datetime(2026, 1, 8, tzinfo=UTC),
    )
    db_session.add_all([older_run, newer_run])
    db_session.commit()
    db_session.refresh(older_run)
    db_session.refresh(newer_run)

    older_suggestion = FeedDiscoverySuggestion(
        run_id=older_run.id,
        user_id=test_user.id,
        suggestion_type="atom",
        site_url="https://older.example.com",
        feed_url="https://older.example.com/feed.xml",
        title="Older Feed",
        status="new",
        config={"feed_url": "https://older.example.com/feed.xml"},
    )
    newer_suggestion = FeedDiscoverySuggestion(
        run_id=newer_run.id,
        user_id=test_user.id,
        suggestion_type="podcast_rss",
        site_url="https://newer.example.com",
        feed_url="https://newer.example.com/rss.xml",
        title="Newer Podcast",
        status="new",
        config={"feed_url": "https://newer.example.com/rss.xml"},
    )
    db_session.add_all([older_suggestion, newer_suggestion])
    db_session.commit()

    response = client.get("/api/discovery/history?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert len(data["runs"]) == 2
    assert data["runs"][0]["run_id"] == newer_run.id
    assert len(data["runs"][0]["podcasts"]) == 1
    assert data["runs"][1]["run_id"] == older_run.id
    assert len(data["runs"][1]["feeds"]) == 1
