"""Unit tests for voice orchestrator STT error handling."""

from __future__ import annotations

import asyncio

import pytest

from app.services.voice.orchestrator import VoiceConversationOrchestrator


async def _emit_event(_payload: dict[str, object]) -> bool:
    return True


@pytest.mark.asyncio
async def test_raise_pending_stt_errors_ignores_commit_too_soon_error() -> None:
    """Recoverable STT commit-too-soon errors should not raise."""

    orchestrator = VoiceConversationOrchestrator(
        session_id="session-test",
        user_id=123,
        emit_event=_emit_event,
    )

    await orchestrator._stt_error_queue.put(
        "Commit request ignored: only 0.00s of uncommitted audio."
    )

    await orchestrator._raise_pending_stt_errors()


@pytest.mark.asyncio
async def test_raise_pending_stt_errors_raises_for_non_recoverable_error() -> None:
    """Non-recoverable STT errors should still raise."""

    orchestrator = VoiceConversationOrchestrator(
        session_id="session-test",
        user_id=123,
        emit_event=_emit_event,
    )

    await orchestrator._stt_error_queue.put("connection reset by peer")

    with pytest.raises(RuntimeError, match="STT error: connection reset by peer"):
        await orchestrator._raise_pending_stt_errors()


@pytest.mark.asyncio
async def test_process_intro_turn_emits_turn_cancelled_on_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelled intro turns should emit turn.cancelled before bubbling cancellation."""

    events: list[dict[str, object]] = []

    async def emit_event(payload: dict[str, object]) -> bool:
        events.append(payload)
        return True

    orchestrator = VoiceConversationOrchestrator(
        session_id="session-test",
        user_id=123,
        emit_event=emit_event,
    )

    async def slow_tts(_turn_id: str, _text: str) -> bool:
        await asyncio.sleep(60)
        return True

    monkeypatch.setattr(orchestrator, "_stream_text_to_tts", slow_tts)

    task = asyncio.create_task(
        orchestrator.process_intro_turn(
            "turn_intro_1",
            "Hello there",
            is_onboarding=False,
        )
    )
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert any(
        event.get("type") == "turn.cancelled" and event.get("turn_id") == "turn_intro_1"
        for event in events
    )
