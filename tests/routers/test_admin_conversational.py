"""Tests for admin conversational routes."""

from __future__ import annotations

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.deps import require_admin
from app.main import app
from app.routers import auth


def test_admin_conversational_page_requires_admin_session(client) -> None:
    """Conversational page should redirect to admin login without admin session."""
    response = client.get("/admin/conversational", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/auth/admin/login?next=")


def test_admin_conversational_health_requires_admin_session(client) -> None:
    """Health endpoint should redirect to admin login without admin session."""
    response = client.get("/admin/conversational/health", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/auth/admin/login?next=")


def test_admin_conversational_health_returns_flags(client, test_user, monkeypatch) -> None:
    """Health endpoint should return readiness payload for authenticated admin."""

    def override_require_admin():
        return test_user

    app.dependency_overrides[require_admin] = override_require_admin
    monkeypatch.setattr(
        "app.routers.admin.build_health_flags",
        lambda: {
            "elevenlabs_api_configured": True,
            "elevenlabs_package_available": True,
            "agent_id": "agent_4701khf4v6jef3vskb8sd2a30m36",
            "agent_text_only": True,
            "ready": True,
        },
    )
    try:
        response = client.get("/admin/conversational/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["ready"] is True
        assert payload["agent_id"] == "agent_4701khf4v6jef3vskb8sd2a30m36"
    finally:
        app.dependency_overrides.pop(require_admin, None)


def test_admin_conversational_ws_rejects_missing_admin_cookie(client) -> None:
    """Websocket endpoint should reject unauthenticated admin sessions."""
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/admin/conversational/ws"):
        pass


def test_admin_conversational_ws_streams_turn_events(client, test_user, monkeypatch) -> None:
    """Websocket endpoint should stream turn events for a valid admin session."""

    started_sessions: list[tuple[str, int]] = []
    closed_runtimes: list[dict[str, int | str]] = []

    def fake_start_agent_session(
        session_id: str,
        user_id: int,
        bootstrap_context: str | None = None,
    ) -> dict[str, int | str]:
        assert isinstance(bootstrap_context, str)
        started_sessions.append((session_id, user_id))
        return {"session_id": session_id, "user_id": user_id}

    def fake_stream_agent_turn(
        runtime: dict[str, int | str],
        user_text: str,
        turn_id: str,
        emit_event,
        knowledge_hits=None,
        web_hits=None,
    ) -> None:
        assert runtime["session_id"]
        assert runtime["user_id"] == test_user.id
        assert user_text == "hello"
        assert knowledge_hits == []
        assert web_hits == []
        emit_event({"type": "assistant_delta", "turn_id": turn_id, "text_delta": "Hello"})
        emit_event({"type": "assistant_final", "turn_id": turn_id, "text": "Hello there"})
        emit_event(
            {
                "type": "audio_chunk_raw",
                "turn_id": turn_id,
                "seq": 0,
                "mime_type": "audio/pcm;rate=16000;channels=1",
                "audio_bytes": b"\x00\x01",
            }
        )
        emit_event({"type": "audio_end", "turn_id": turn_id, "total_chunks": 1})

    def fake_close_agent_session(runtime: dict[str, int | str]) -> None:
        closed_runtimes.append(runtime)

    monkeypatch.setattr(
        "app.routers.admin.search_knowledge",
        lambda db, user_id, query, limit=5: [],
    )
    monkeypatch.setattr("app.routers.admin.search_web", lambda query, limit=5: [])
    monkeypatch.setattr("app.routers.admin.start_agent_session", fake_start_agent_session)
    monkeypatch.setattr("app.routers.admin.stream_agent_turn", fake_stream_agent_turn)
    monkeypatch.setattr("app.routers.admin.close_agent_session", fake_close_agent_session)

    token = "test-admin-token"
    auth.admin_sessions.add(token)
    client.cookies.set("admin_session", token)

    try:
        with client.websocket_connect("/admin/conversational/ws") as websocket:
            websocket.send_json({"type": "init", "user_id": test_user.id})
            ready = websocket.receive_json()
            assert ready["type"] == "ready"
            assert ready["session_id"]

            websocket.send_json(
                {
                    "type": "user_message",
                    "turn_id": "turn_123",
                    "text": "hello",
                }
            )

            events = []
            while True:
                payload = websocket.receive_json()
                events.append(payload)
                if payload.get("type") == "turn_complete":
                    break

            event_types = [event["type"] for event in events]
            assert event_types[0] == "turn_started"
            assert "sources" in event_types
            assert "assistant_delta" in event_types
            assert "assistant_final" in event_types
            assert "audio_chunk" in event_types
            assert "audio_end" in event_types
            assert event_types[-1] == "turn_complete"
        assert len(started_sessions) == 1
        assert len(closed_runtimes) == 1
    finally:
        auth.admin_sessions.discard(token)
        client.cookies.pop("admin_session", None)
