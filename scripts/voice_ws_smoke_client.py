"""Small smoke client for /api/voice websocket behavior.

Usage:
    uv run python scripts/voice_ws_smoke_client.py
    uv run python scripts/voice_ws_smoke_client.py --mode real
"""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import base64
import sys
import time
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.db import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.user import User
from app.routers.api import voice as voice_router


class _StubOrchestrator:
    """Deterministic orchestrator for protocol smoke tests."""

    def __init__(
        self,
        *,
        session_id: str,
        user_id: int,
        emit_event,
        chat_session_id: str | None = None,
        launch_mode: str = "general",
        content_context: str | None = None,
        sample_rate_hz: int = 16_000,
    ) -> None:
        _ = (
            session_id,
            user_id,
            chat_session_id,
            launch_mode,
            content_context,
            sample_rate_hz,
        )
        self.emit_event = emit_event

    async def start(self) -> None:
        return

    async def close(self) -> None:
        return

    async def handle_audio_frame(self, _pcm16_b64: str) -> None:
        await self.emit_event({"type": "transcript.partial", "text": "hel"})

    async def process_turn(self, turn_id: str) -> dict[str, Any]:
        await self.emit_event({"type": "turn.started", "turn_id": turn_id})
        await self.emit_event({"type": "transcript.final", "turn_id": turn_id, "text": "hello"})
        await self.emit_event({"type": "assistant.text.delta", "turn_id": turn_id, "text": "Hi"})
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
                "latency_ms": 12,
                "transcript_chars": 5,
                "response_chars": 8,
                "model": "anthropic:claude-haiku-4-5-20251001",
            }
        )
        return {}


def _ensure_user_token() -> str:
    """Create/fetch a local test user and return bearer token."""

    with get_db() as db:
        user = db.query(User).filter(User.email == "voice_smoke@example.com").first()
        if user is None:
            user = User(
                apple_id="voice_smoke_user",
                email="voice_smoke@example.com",
                full_name="Voice Smoke",
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return create_access_token(int(user.id))


def _build_pcm16_silence_b64(
    *,
    duration_seconds: float,
    sample_rate_hz: int,
) -> str:
    """Return base64 PCM16 silence long enough for STT commit."""

    sample_count = max(1, int(duration_seconds * sample_rate_hz))
    pcm_bytes = b"\x00\x00" * sample_count
    return base64.b64encode(pcm_bytes).decode("ascii")


def run_smoke(mode: str) -> None:
    """Run one websocket smoke exchange and print resulting event types."""

    token = _ensure_user_token()
    headers = {"Authorization": f"Bearer {token}"}
    sample_rate_hz = 16_000
    pcm16_b64 = (
        _build_pcm16_silence_b64(duration_seconds=0.4, sample_rate_hz=sample_rate_hz)
        if mode == "real"
        else "AA=="
    )

    original_orchestrator = voice_router.VoiceConversationOrchestrator
    if mode == "stub":
        voice_router.VoiceConversationOrchestrator = _StubOrchestrator

    try:
        with TestClient(app) as client:
            created = client.post(
                "/api/voice/sessions",
                headers=headers,
                json={"sample_rate_hz": sample_rate_hz},
            )
            payload = created.json()
            print(f"create_status={created.status_code} session_id={payload['session_id']}")

            events: list[dict[str, Any]] = []
            with client.websocket_connect(payload["websocket_path"], headers=headers) as ws:
                events.append(ws.receive_json())
                ws.send_json({"type": "session.start", "session_id": payload["session_id"]})
                ws.send_json(
                    {
                        "type": "audio.frame",
                        "seq": 0,
                        "pcm16_b64": pcm16_b64,
                        "sample_rate_hz": sample_rate_hz,
                        "channels": 1,
                    }
                )
                if mode == "real":
                    time.sleep(0.4)
                ws.send_json({"type": "audio.commit", "seq": 0})

                for _ in range(10):
                    event = ws.receive_json()
                    events.append(event)
                    if event.get("type") in {"turn.completed", "turn.cancelled", "error"}:
                        break

            print("event_types=", [event.get("type") for event in events])
            if events and events[-1].get("type") == "error":
                print("error_event=", events[-1])
    finally:
        voice_router.VoiceConversationOrchestrator = original_orchestrator


def main() -> None:
    """Parse args and run smoke validation."""

    parser = argparse.ArgumentParser(description="Smoke client for /api/voice websocket flow")
    parser.add_argument(
        "--mode",
        choices=("stub", "real"),
        default="stub",
        help="stub=deterministic protocol test, real=actual STT/LLM/TTS pipeline",
    )
    args = parser.parse_args()
    run_smoke(args.mode)


if __name__ == "__main__":
    main()
