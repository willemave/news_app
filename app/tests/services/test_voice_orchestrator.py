"""Unit tests for voice orchestrator STT error handling."""

from __future__ import annotations

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
