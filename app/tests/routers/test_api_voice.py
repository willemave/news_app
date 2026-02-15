"""Tests for public voice API routes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.routers.api import voice as voice_router
from app.services.voice.session_manager import clear_voice_sessions


@pytest.fixture(autouse=True)
def reset_voice_sessions() -> None:
    """Ensure voice session store is isolated per test."""

    clear_voice_sessions()
    yield
    clear_voice_sessions()


def test_create_voice_session(client) -> None:
    """Authenticated user can create voice session metadata."""

    response = client.post("/api/voice/sessions", json={"sample_rate_hz": 16000})
    assert response.status_code == 200

    payload = response.json()
    assert payload["session_id"]
    assert payload["websocket_path"].startswith("/api/voice/ws/")
    assert payload["sample_rate_hz"] == 16000
    assert payload["audio_format"] == "pcm16"
    assert payload["chat_session_id"] > 0
    assert payload["launch_mode"] == "general"
    assert payload["content_context_attached"] is False


def test_voice_health_returns_flags(client, monkeypatch) -> None:
    """Voice health endpoint should return provider capability flags."""

    monkeypatch.setattr(
        "app.routers.api.voice.build_voice_health_flags",
        lambda: {
            "ready": True,
            "elevenlabs_api_configured": True,
            "elevenlabs_package_available": True,
            "anthropic_api_configured": True,
            "exa_api_configured": True,
            "stt_model_id": "scribe_v2_realtime",
            "tts_voice_id": "voice_123",
            "tts_model_id": "eleven_multilingual_v2",
            "tts_output_format": "pcm_16000",
            "readiness_reasons": [],
        },
    )

    response = client.get("/api/voice/health")
    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_voice_websocket_requires_bearer_token(client) -> None:
    """Voice websocket should reject missing authorization."""

    created = client.post("/api/voice/sessions", json={})
    session_id = created.json()["session_id"]

    with pytest.raises(WebSocketDisconnect), client.websocket_connect(
        f"/api/voice/ws/{session_id}"
    ):
        pass


def test_voice_websocket_streams_turn_events(client, test_user, monkeypatch) -> None:
    """Voice websocket should emit expected events for one turn."""

    class FakeOrchestrator:
        def __init__(
            self,
            *,
            session_id: str,
            user_id: int,
            emit_event,
            chat_session_id: int | None = None,
            launch_mode: str = "general",
            content_context: str | None = None,
            sample_rate_hz: int = 16_000,
        ) -> None:
            self.session_id = session_id
            self.user_id = user_id
            self.emit_event = emit_event
            self.chat_session_id = chat_session_id
            self.launch_mode = launch_mode
            self.content_context = content_context
            self.sample_rate_hz = sample_rate_hz
            self.audio_frames: list[str] = []

        async def start(self) -> None:
            return

        async def close(self) -> None:
            return

        async def handle_audio_frame(self, pcm16_b64: str) -> None:
            self.audio_frames.append(pcm16_b64)
            await self.emit_event({"type": "transcript.partial", "text": "te"})

        async def process_turn(self, turn_id: str) -> dict[str, Any]:
            await self.emit_event({"type": "turn.started", "turn_id": turn_id})
            await self.emit_event({"type": "transcript.final", "turn_id": turn_id, "text": "test"})
            await self.emit_event(
                {
                    "type": "assistant.text.delta",
                    "turn_id": turn_id,
                    "text": "Hi",
                }
            )
            await self.emit_event(
                {
                    "type": "assistant.audio.chunk",
                    "turn_id": turn_id,
                    "seq": 0,
                    "audio_b64": "AA==",
                    "format": "pcm_16000",
                }
            )
            await self.emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": "Hi there",
                }
            )
            await self.emit_event({"type": "assistant.audio.final", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "turn.completed",
                    "turn_id": turn_id,
                    "latency_ms": 9,
                    "transcript_chars": 4,
                    "response_chars": 8,
                    "model": "anthropic:claude-haiku-4-5-20251001",
                }
            )
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", FakeOrchestrator)

    created = client.post("/api/voice/sessions", json={})
    session_id = created.json()["session_id"]
    token = create_access_token(test_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/api/voice/ws/{session_id}", headers=headers) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"
        assert ready["session_id"] == session_id
        assert ready["chat_session_id"] == created.json()["chat_session_id"]
        assert ready["launch_mode"] == "general"

        websocket.send_json({"type": "session.start", "session_id": session_id})
        websocket.send_json(
            {
                "type": "audio.frame",
                "seq": 0,
                "pcm16_b64": "AA==",
                "sample_rate_hz": 16000,
                "channels": 1,
            }
        )
        partial = websocket.receive_json()
        assert partial["type"] == "transcript.partial"

        websocket.send_json({"type": "audio.commit", "seq": 0})
        event_types: list[str] = []
        while True:
            payload = websocket.receive_json()
            event_types.append(payload["type"])
            if payload["type"] == "turn.completed":
                break

        assert "turn.started" in event_types
        assert "transcript.final" in event_types
        assert "assistant.text.delta" in event_types
        assert "assistant.audio.chunk" in event_types
        assert "assistant.text.final" in event_types
        assert "assistant.audio.final" in event_types
        assert event_types[-1] == "turn.completed"


def test_voice_websocket_auto_runs_dictate_summary_turn(
    client, test_user, monkeypatch
) -> None:
    """Dictate-summary sessions should start with an automatic seeded summary turn."""

    class FakeOrchestrator:
        def __init__(
            self,
            *,
            session_id: str,
            user_id: int,
            emit_event,
            chat_session_id: int | None = None,
            launch_mode: str = "general",
            content_context: str | None = None,
            sample_rate_hz: int = 16_000,
        ) -> None:
            self.session_id = session_id
            self.user_id = user_id
            self.emit_event = emit_event
            self.chat_session_id = chat_session_id
            self.launch_mode = launch_mode
            self.content_context = content_context
            self.sample_rate_hz = sample_rate_hz

        async def start(self) -> None:
            return

        async def close(self) -> None:
            return

        async def handle_audio_frame(self, pcm16_b64: str) -> None:
            _ = pcm16_b64
            return

        async def process_turn(self, turn_id: str) -> dict[str, Any]:
            _ = turn_id
            return {}

        async def process_text_turn(self, turn_id: str, user_text: str) -> dict[str, Any]:
            await self.emit_event({"type": "turn.started", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "transcript.final",
                    "turn_id": turn_id,
                    "text": user_text,
                }
            )
            await self.emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": "Here is your summary.",
                }
            )
            await self.emit_event({"type": "assistant.audio.final", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "turn.completed",
                    "turn_id": turn_id,
                    "latency_ms": 7,
                    "transcript_chars": len(user_text),
                    "response_chars": 21,
                    "model": "anthropic:claude-haiku-4-5-20251001",
                }
            )
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        voice_router,
        "load_voice_content_context",
        lambda db, user_id, content_id: SimpleNamespace(
            content_id=content_id,
            title="Sample Item",
            url="https://example.com/item",
            source="Example",
            summary="A short summary",
            transcript_excerpt=None,
        ),
    )
    monkeypatch.setattr(
        voice_router,
        "format_voice_content_context",
        lambda context: f"title: {context.title}\nsummary: {context.summary}",
    )

    created = client.post(
        "/api/voice/sessions",
        json={
            "launch_mode": "dictate_summary",
            "content_id": 1,
        },
    )
    assert created.status_code == 200

    session_id = created.json()["session_id"]
    token = create_access_token(test_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/api/voice/ws/{session_id}", headers=headers) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"
        assert ready["launch_mode"] == "dictate_summary"

        websocket.send_json({"type": "session.start", "session_id": session_id})

        payload = websocket.receive_json()
        assert payload["type"] == "turn.started"

        payload = websocket.receive_json()
        assert payload["type"] == "transcript.final"
        assert "concise spoken summary" in payload["text"]

        event_types: list[str] = [payload["type"]]
        while True:
            payload = websocket.receive_json()
            event_types.append(payload["type"])
            if payload["type"] == "turn.completed":
                break

        assert "assistant.text.final" in event_types
        assert "assistant.audio.final" in event_types
