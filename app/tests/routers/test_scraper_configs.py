from app.constants import DEFAULT_NEW_FEED_LIMIT
from app.models.schema import UserScraperConfig


def test_scraper_configs_crud(client, db_session, test_user):
    create_payload = {
        "scraper_type": "substack",
        "display_name": "My Substack",
        "config": {"feed_url": "https://example.com/feed"},
        "is_active": True,
    }
    create_resp = client.post("/api/scrapers", json=create_payload)
    assert create_resp.status_code == 201
    created = create_resp.json()
    config_id = created["id"]
    assert created["scraper_type"] == "substack"
    assert created["feed_url"] == "https://example.com/feed"
    assert created["limit"] == DEFAULT_NEW_FEED_LIMIT

    list_resp = client.get("/api/scrapers")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 1
    assert data[0]["config"]["feed_url"] == "https://example.com/feed"
    assert data[0]["feed_url"] == "https://example.com/feed"

    update_resp = client.put(f"/api/scrapers/{config_id}", json={"is_active": False})
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False

    delete_resp = client.delete(f"/api/scrapers/{config_id}")
    assert delete_resp.status_code == 204

    db_session.expire_all()
    remaining = db_session.query(UserScraperConfig).all()
    assert remaining == []


def test_scraper_configs_filtering_and_limits(client, test_user):
    # Create a feed and a podcast config
    client.post(
        "/api/scrapers",
        json={
            "scraper_type": "substack",
            "display_name": "My Substack",
            "config": {"feed_url": "https://example.com/feed"},
            "is_active": True,
        },
    )
    podcast_resp = client.post(
        "/api/scrapers",
        json={
            "scraper_type": "podcast_rss",
            "display_name": "My Podcast",
            "config": {"feed_url": "https://pod.example.com/rss", "limit": 15},
            "is_active": True,
        },
    )
    assert podcast_resp.status_code == 201
    podcast_data = podcast_resp.json()
    assert podcast_data["limit"] == 15

    # Filter by type
    type_resp = client.get("/api/scrapers?type=podcast_rss")
    assert type_resp.status_code == 200
    filtered = type_resp.json()
    assert len(filtered) == 1
    assert filtered[0]["scraper_type"] == "podcast_rss"
    assert filtered[0]["feed_url"] == "https://pod.example.com/rss"
    assert filtered[0]["limit"] == 15

    # Multiple types
    multi_resp = client.get("/api/scrapers?types=podcast_rss,atom")
    assert multi_resp.status_code == 200
    assert len(multi_resp.json()) == 1

    # Invalid type
    bad_resp = client.get("/api/scrapers?type=invalid_type")
    assert bad_resp.status_code == 400
    assert "Unsupported scraper types" in bad_resp.json()["detail"]


def test_scraper_config_limit_validation(client, test_user):
    bad_resp = client.post(
        "/api/scrapers",
        json={
            "scraper_type": "podcast_rss",
            "display_name": "Bad Limit",
            "config": {"feed_url": "https://pod.example.com/rss", "limit": 0},
            "is_active": True,
        },
    )
    # Pydantic validation errors return 422
    assert bad_resp.status_code == 422

    ok_resp = client.post(
        "/api/scrapers",
        json={
            "scraper_type": "podcast_rss",
            "display_name": "Good Limit",
            "config": {"feed_url": "https://pod.example.com/rss", "limit": 25},
            "is_active": True,
        },
    )
    assert ok_resp.status_code == 201
    assert ok_resp.json()["limit"] == 25


def test_subscribe_feed_defaults_limit(client, test_user):
    resp = client.post(
        "/api/scrapers/subscribe",
        json={
            "feed_url": "https://example.com/feed.xml",
            "feed_type": "atom",
            "display_name": "Example Feed",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["limit"] == DEFAULT_NEW_FEED_LIMIT
