"""Tests for public voice API routes."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
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


def _wait_for_condition(
    predicate: Callable[[], bool],
    timeout_seconds: float = 3.0,
    interval_seconds: float = 0.01,
) -> bool:
    """Poll until predicate returns true or timeout is reached."""

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval_seconds)
    return predicate()


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


def test_create_voice_session_allows_dictate_summary_for_article(
    client, monkeypatch
) -> None:
    """Dictate-summary can be created for article content."""

    monkeypatch.setattr(
        voice_router,
        "load_voice_content_context",
        lambda db, user_id, content_id, include_summary_narration=False: SimpleNamespace(
            content_id=content_id,
            title="Article",
            url="https://example.com/article",
            source="example.com",
            summary="Summary",
            transcript_excerpt=None,
            summary_narration="Narrative. Point 1. Point 2." if include_summary_narration else None,
        ),
    )

    response = client.post(
        "/api/voice/sessions",
        json={
            "launch_mode": "dictate_summary",
            "content_id": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["launch_mode"] == "dictate_summary"
    assert payload["content_context_attached"] is True


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
    """Dictate-summary sessions should auto-start with prebuilt summary narration."""

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

        async def process_scripted_turn(
            self,
            turn_id: str,
            assistant_text: str,
            *,
            model: str = "system:scripted",
        ) -> dict[str, Any]:
            await self.emit_event({"type": "turn.started", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": assistant_text,
                }
            )
            await self.emit_event({"type": "assistant.audio.final", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "turn.completed",
                    "turn_id": turn_id,
                    "latency_ms": 7,
                    "transcript_chars": 0,
                    "response_chars": len(assistant_text),
                    "model": model,
                }
            )
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        voice_router,
        "load_voice_content_context",
        lambda db, user_id, content_id, include_summary_narration=False: SimpleNamespace(
            content_id=content_id,
            title="Sample Item",
            url="https://example.com/item",
            source="Example",
            summary="A short summary",
            transcript_excerpt=None,
            summary_narration="Narrative. Point 1. Point 2." if include_summary_narration else None,
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
        assert payload["type"] == "assistant.text.final"
        assert "Point 1" in payload["text"]

        event_types: list[str] = [payload["type"]]
        while True:
            payload = websocket.receive_json()
            event_types.append(payload["type"])
            if payload["type"] == "turn.completed":
                break

        assert "assistant.text.final" in event_types
        assert "assistant.audio.final" in event_types


def test_voice_websocket_dictate_summary_rejects_audio_input(
    client, test_user, monkeypatch
) -> None:
    """Dictate-summary mode should be read-only and reject microphone events."""

    audio_frame_calls = {"count": 0}

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
            self.emit_event = emit_event
            _ = (
                session_id,
                user_id,
                chat_session_id,
                launch_mode,
                content_context,
                sample_rate_hz,
            )

        async def start(self) -> None:
            return

        async def close(self) -> None:
            return

        async def handle_audio_frame(self, pcm16_b64: str) -> None:
            _ = pcm16_b64
            audio_frame_calls["count"] += 1

        async def process_turn(self, turn_id: str) -> dict[str, Any]:
            _ = turn_id
            return {}

        async def process_scripted_turn(
            self,
            turn_id: str,
            assistant_text: str,
            *,
            model: str = "system:scripted",
        ) -> dict[str, Any]:
            await self.emit_event({"type": "turn.started", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": assistant_text,
                }
            )
            await self.emit_event({"type": "assistant.audio.final", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "turn.completed",
                    "turn_id": turn_id,
                    "latency_ms": 5,
                    "transcript_chars": 0,
                    "response_chars": len(assistant_text),
                    "model": model,
                }
            )
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        voice_router,
        "load_voice_content_context",
        lambda db, user_id, content_id, include_summary_narration=False: SimpleNamespace(
            content_id=content_id,
            title="Sample Item",
            url="https://example.com/item",
            source="Example",
            summary="A short summary",
            transcript_excerpt=None,
            summary_narration="Narrative. Point 1. Point 2." if include_summary_narration else None,
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

        websocket.send_json({"type": "session.start", "session_id": session_id})

        while True:
            payload = websocket.receive_json()
            if payload["type"] == "turn.completed":
                break

        websocket.send_json(
            {
                "type": "audio.frame",
                "seq": 0,
                "pcm16_b64": "AA==",
                "sample_rate_hz": 16000,
                "channels": 1,
            }
        )
        frame_error = websocket.receive_json()
        assert frame_error["type"] == "error"
        assert frame_error["code"] == "read_only_mode"
        assert frame_error["retryable"] is False

        websocket.send_json({"type": "audio.commit", "seq": 0})
        commit_error = websocket.receive_json()
        assert commit_error["type"] == "error"
        assert commit_error["code"] == "read_only_mode"
        assert commit_error["retryable"] is False

        assert audio_frame_calls["count"] == 0


def test_voice_websocket_auto_runs_dictate_summary_after_returning_intro(
    client, db_session, test_user, monkeypatch
) -> None:
    """Dictate-summary should auto-start narration after non-onboarding intro."""

    test_user.has_completed_live_voice_onboarding = True
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    scripted_turn_calls = {"count": 0}

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
            self.emit_event = emit_event
            _ = (
                session_id,
                user_id,
                chat_session_id,
                launch_mode,
                content_context,
                sample_rate_hz,
            )

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

        async def process_intro_turn(
            self,
            turn_id: str,
            intro_text: str,
            *,
            is_onboarding: bool = True,
        ) -> dict[str, Any]:
            await self.emit_event(
                {
                    "type": "turn.started",
                    "turn_id": turn_id,
                    "is_intro": True,
                    "is_onboarding_intro": is_onboarding,
                }
            )
            await self.emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": intro_text,
                }
            )
            await self.emit_event(
                {
                    "type": "assistant.audio.final",
                    "turn_id": turn_id,
                    "tts_enabled": True,
                }
            )
            await self.emit_event(
                {
                    "type": "turn.completed",
                    "turn_id": turn_id,
                    "latency_ms": 5,
                    "transcript_chars": 0,
                    "response_chars": len(intro_text),
                    "model": "system:intro",
                }
            )
            return {}

        async def process_scripted_turn(
            self,
            turn_id: str,
            assistant_text: str,
            *,
            model: str = "system:scripted",
        ) -> dict[str, Any]:
            _ = model
            scripted_turn_calls["count"] += 1
            await self.emit_event({"type": "turn.started", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": assistant_text,
                }
            )
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        voice_router,
        "load_voice_content_context",
        lambda db, user_id, content_id, include_summary_narration=False: SimpleNamespace(
            content_id=content_id,
            title="Sample Item",
            url="https://example.com/item",
            source="Example",
            summary="A short summary",
            transcript_excerpt=None,
            summary_narration="Narrative. Point 1. Point 2." if include_summary_narration else None,
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
            "request_intro": True,
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

        intro_started = websocket.receive_json()
        assert intro_started["type"] == "turn.started"
        assert intro_started.get("is_intro") is True
        assert intro_started.get("is_onboarding_intro") is False

        while True:
            payload = websocket.receive_json()
            if payload["type"] == "turn.completed":
                break

        assert _wait_for_condition(lambda: scripted_turn_calls["count"] == 1)


def test_voice_websocket_onboarding_requires_intro_ack_for_auto_summary(
    client, db_session, test_user, monkeypatch
) -> None:
    """Onboarding intro should gate dictate-summary auto run until intro.ack."""

    test_user.has_completed_live_voice_onboarding = False
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    scripted_turn_calls = {"count": 0}

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
            self.emit_event = emit_event
            _ = (
                session_id,
                user_id,
                chat_session_id,
                launch_mode,
                content_context,
                sample_rate_hz,
            )

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

        async def process_intro_turn(
            self,
            turn_id: str,
            intro_text: str,
            *,
            is_onboarding: bool = True,
        ) -> dict[str, Any]:
            await self.emit_event(
                {
                    "type": "turn.started",
                    "turn_id": turn_id,
                    "is_intro": True,
                    "is_onboarding_intro": is_onboarding,
                }
            )
            await self.emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": intro_text,
                }
            )
            await self.emit_event({"type": "assistant.audio.final", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "turn.completed",
                    "turn_id": turn_id,
                    "latency_ms": 5,
                    "transcript_chars": 0,
                    "response_chars": len(intro_text),
                    "model": "system:intro",
                }
            )
            return {}

        async def process_scripted_turn(
            self,
            turn_id: str,
            assistant_text: str,
            *,
            model: str = "system:scripted",
        ) -> dict[str, Any]:
            _ = model
            scripted_turn_calls["count"] += 1
            await self.emit_event({"type": "turn.started", "turn_id": turn_id})
            await self.emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": assistant_text,
                }
            )
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", FakeOrchestrator)
    monkeypatch.setattr(
        voice_router,
        "load_voice_content_context",
        lambda db, user_id, content_id, include_summary_narration=False: SimpleNamespace(
            content_id=content_id,
            title="Sample Item",
            url="https://example.com/item",
            source="Example",
            summary="A short summary",
            transcript_excerpt=None,
            summary_narration="Narrative. Point 1. Point 2." if include_summary_narration else None,
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
            "request_intro": True,
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

        intro_started = websocket.receive_json()
        assert intro_started["type"] == "turn.started"
        assert intro_started.get("is_intro") is True
        assert intro_started.get("is_onboarding_intro") is True

        while True:
            payload = websocket.receive_json()
            if payload["type"] == "turn.completed":
                break

        assert not _wait_for_condition(lambda: scripted_turn_calls["count"] == 1)

        websocket.send_json({"type": "intro.ack"})
        ack = websocket.receive_json()
        assert ack["type"] == "intro.acknowledged"

        assert _wait_for_condition(lambda: scripted_turn_calls["count"] == 1)


def test_voice_websocket_reports_start_failure_without_crashing(
    client, test_user, monkeypatch
) -> None:
    """Websocket should emit non-retryable error if STT stream setup fails."""

    class FailingOrchestrator:
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
            _ = (
                session_id,
                user_id,
                emit_event,
                chat_session_id,
                launch_mode,
                content_context,
                sample_rate_hz,
            )

        async def start(self) -> None:
            raise RuntimeError("ElevenLabs API key is not configured")

        async def close(self) -> None:
            return

        async def handle_audio_frame(self, pcm16_b64: str) -> None:
            _ = pcm16_b64
            return

        async def process_turn(self, turn_id: str) -> dict[str, Any]:
            _ = turn_id
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", FailingOrchestrator)

    created = client.post("/api/voice/sessions", json={})
    session_id = created.json()["session_id"]
    token = create_access_token(test_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/api/voice/ws/{session_id}", headers=headers) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"

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

        error_payload = websocket.receive_json()
        assert error_payload["type"] == "error"
        assert error_payload["code"] == "voice_stream_unavailable"
        assert error_payload["retryable"] is False


def test_voice_websocket_reports_audio_frame_failure_without_crashing(
    client, test_user, monkeypatch
) -> None:
    """Audio frame forwarding failures should return a retryable websocket error."""

    class FrameFailingOrchestrator:
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
            _ = (
                session_id,
                user_id,
                emit_event,
                chat_session_id,
                launch_mode,
                content_context,
                sample_rate_hz,
            )

        async def start(self) -> None:
            return

        async def close(self) -> None:
            return

        async def handle_audio_frame(self, pcm16_b64: str) -> None:
            _ = pcm16_b64
            raise RuntimeError("received 1008 invalid_request")

        async def process_turn(self, turn_id: str) -> dict[str, Any]:
            _ = turn_id
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", FrameFailingOrchestrator)

    created = client.post("/api/voice/sessions", json={})
    session_id = created.json()["session_id"]
    token = create_access_token(test_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/api/voice/ws/{session_id}", headers=headers) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"

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

        error_payload = websocket.receive_json()
        assert error_payload["type"] == "error"
        assert error_payload["code"] == "audio_frame_rejected"
        assert error_payload["retryable"] is True


def test_voice_websocket_acknowledges_response_cancel_without_active_turn(
    client, test_user
) -> None:
    """Cancelling without an active turn should return a completed acknowledgement."""

    created = client.post("/api/voice/sessions", json={})
    session_id = created.json()["session_id"]
    token = create_access_token(test_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/api/voice/ws/{session_id}", headers=headers) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"

        websocket.send_json({"type": "session.start", "session_id": session_id})
        websocket.send_json({"type": "response.cancel"})
        payload = websocket.receive_json()
        assert payload["type"] == "response.cancelled"
        assert payload["reason"] == "already_completed"
        assert payload.get("turn_id") is None


def test_voice_websocket_session_start_mismatch_does_not_start_turn(
    client, test_user
) -> None:
    """A mismatched session.start must not trigger intro/turn processing."""

    created = client.post("/api/voice/sessions", json={})
    session_id = created.json()["session_id"]
    token = create_access_token(test_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/api/voice/ws/{session_id}", headers=headers) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"

        websocket.send_json({"type": "session.start", "session_id": "wrong-session-id"})
        mismatch = websocket.receive_json()
        assert mismatch["type"] == "error"
        assert mismatch["code"] == "session_mismatch"

        websocket.send_json({"type": "response.cancel"})
        payload = websocket.receive_json()
        assert payload["type"] == "response.cancelled"
        assert payload["reason"] == "already_completed"
        assert payload.get("turn_id") is None


def test_voice_websocket_acknowledges_response_cancel_for_active_turn(
    client, test_user, monkeypatch
) -> None:
    """Cancelling an active turn should emit turn.cancelled and response.cancelled."""

    class CancellableOrchestrator:
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
            self.emit_event = emit_event
            _ = (
                session_id,
                user_id,
                chat_session_id,
                launch_mode,
                content_context,
                sample_rate_hz,
            )

        async def start(self) -> None:
            return

        async def close(self) -> None:
            return

        async def handle_audio_frame(self, pcm16_b64: str) -> None:
            _ = pcm16_b64
            return

        async def process_turn(self, turn_id: str) -> dict[str, Any]:
            await self.emit_event({"type": "turn.started", "turn_id": turn_id})
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                await self.emit_event(
                    {"type": "turn.cancelled", "turn_id": turn_id, "reason": "client_cancelled"}
                )
                raise
            return {}

    monkeypatch.setattr(voice_router, "VoiceConversationOrchestrator", CancellableOrchestrator)

    created = client.post("/api/voice/sessions", json={})
    session_id = created.json()["session_id"]
    token = create_access_token(test_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    with client.websocket_connect(f"/api/voice/ws/{session_id}", headers=headers) as websocket:
        ready = websocket.receive_json()
        assert ready["type"] == "session.ready"

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
        websocket.send_json({"type": "audio.commit", "seq": 0})

        turn_started = websocket.receive_json()
        assert turn_started["type"] == "turn.started"
        turn_id = turn_started["turn_id"]

        websocket.send_json({"type": "response.cancel"})
        payloads: list[dict[str, Any]] = []
        while True:
            payload = websocket.receive_json()
            payloads.append(payload)
            if payload["type"] == "response.cancelled":
                break

        assert any(item["type"] == "turn.cancelled" for item in payloads)
        cancel_ack = payloads[-1]
        assert cancel_ack["type"] == "response.cancelled"
        assert cancel_ack["reason"] == "client_request"
        assert cancel_ack["turn_id"] == turn_id
