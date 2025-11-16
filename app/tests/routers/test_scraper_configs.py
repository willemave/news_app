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

    list_resp = client.get("/api/scrapers")
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 1
    assert data[0]["config"]["feed_url"] == "https://example.com/feed"

    update_resp = client.put(f"/api/scrapers/{config_id}", json={"is_active": False})
    assert update_resp.status_code == 200
    assert update_resp.json()["is_active"] is False

    delete_resp = client.delete(f"/api/scrapers/{config_id}")
    assert delete_resp.status_code == 204

    db_session.expire_all()
    remaining = db_session.query(UserScraperConfig).all()
    assert remaining == []
