"""Tests for /api/integrations/x endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from app.models.schema import UserIntegrationConnection
from app.services.x_integration import XConnectionView


def test_get_x_connection_default_state(client):
    response = client.get("/api/integrations/x/connection")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "x"
    assert data["connected"] is False
    assert data["is_active"] is False
    assert data["provider_username"] is None


def test_start_x_oauth_returns_authorize_url(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.api.integrations.start_x_oauth",
        lambda db, user, twitter_username=None: (
            "https://x.com/i/oauth2/authorize?state=test-state",
            "test-state",
            ["tweet.read", "users.read", "bookmark.read"],
        ),
    )

    response = client.post(
        "/api/integrations/x/oauth/start",
        json={"twitter_username": "@willem_aw"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "test-state"
    assert data["authorize_url"].startswith("https://x.com/i/oauth2/authorize")
    assert "bookmark.read" in data["scopes"]


def test_exchange_x_oauth_returns_connection(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.api.integrations.exchange_x_oauth",
        lambda db, user, code, state: XConnectionView(
            provider="x",
            connected=True,
            is_active=True,
            provider_user_id="12345",
            provider_username="willemaw",
            scopes=["tweet.read", "users.read", "bookmark.read"],
            last_synced_at=datetime.now(UTC),
            last_status="connected",
            last_error=None,
            twitter_username="willemaw",
        ),
    )

    response = client.post(
        "/api/integrations/x/oauth/exchange",
        json={"code": "oauth-code", "state": "oauth-state"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["provider_username"] == "willemaw"
    assert data["twitter_username"] == "willemaw"


def test_disconnect_x_connection_clears_tokens(client, db_session, test_user):
    connection = UserIntegrationConnection(
        user_id=test_user.id,
        provider="x",
        provider_user_id="12345",
        provider_username="willemaw",
        access_token_encrypted="encrypted-access",
        refresh_token_encrypted="encrypted-refresh",
        is_active=True,
    )
    db_session.add(connection)
    db_session.commit()
    db_session.refresh(connection)

    response = client.delete("/api/integrations/x/connection")
    assert response.status_code == 200
    assert response.json()["status"] == "disconnected"

    db_session.refresh(connection)
    assert connection.is_active is False
    assert connection.access_token_encrypted is None
    assert connection.refresh_token_encrypted is None
