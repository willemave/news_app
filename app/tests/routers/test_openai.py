from __future__ import annotations


def test_realtime_token_endpoint(client, monkeypatch):
    def fake_create_secret(*, session=None):
        return ("test-token", 1234567890, "gpt-realtime")

    monkeypatch.setattr(
        "app.services.openai_realtime.create_realtime_client_secret", fake_create_secret
    )

    response = client.post("/api/openai/realtime/token")
    assert response.status_code == 200
    data = response.json()
    assert data["token"] == "test-token"
    assert data["expires_at"] == 1234567890
    assert data["model"] == "gpt-realtime"
