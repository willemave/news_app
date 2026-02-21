"""Realtime voice turn orchestration for STT -> LLM -> TTS streaming."""

from __future__ import annotations

import asyncio
import base64
import queue
import time
from collections.abc import Awaitable, Callable, Iterator
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.voice.agent_streaming import stream_voice_agent_turn
from app.services.voice.elevenlabs_streaming import (
    ElevenLabsSttCallbacks,
    build_realtime_tts_stream,
    close_stt_connection,
    commit_audio,
    next_tts_chunk,
    open_realtime_stt_connection,
    send_audio_frame,
)
from app.services.voice.persistence import persist_voice_turn
from app.services.voice.session_manager import append_message_history, get_message_history

logger = get_logger(__name__)

EventEmitter = Callable[[dict[str, Any]], Awaitable[bool | None]]
MAX_ASSISTANT_CARRYOVER_CHARS = 400
STT_FINAL_STALE_TOLERANCE_SECONDS = 0.05


def _truncate_for_trace(text: str | None) -> str:
    """Bound trace text payloads to keep structured logs compact."""

    if not text:
        return ""
    settings = get_settings()
    max_chars = max(120, int(settings.voice_trace_max_chars))
    max_chars = min(max_chars, 4_000)
    trimmed = text.strip()
    if len(trimmed) <= max_chars:
        return trimmed
    return trimmed[:max_chars].rstrip() + "..."


@dataclass
class TurnOutcome:
    """Outcome details for one completed turn."""

    transcript: str
    assistant_text: str
    latency_ms: int


class _SpeechChunker:
    """Chunk streamed text into TTS-friendly segments."""

    def __init__(self, min_chars: int = 60, max_chars: int = 180) -> None:
        self._buffer = ""
        self._min_chars = min_chars
        self._max_chars = max_chars

    def add_delta(self, text_delta: str) -> list[str]:
        """Add new text and return flush-ready chunks."""

        if not text_delta:
            return []

        self._buffer += text_delta
        chunks: list[str] = []

        while True:
            flush_index = self._find_flush_index(self._buffer)
            if flush_index <= 0:
                break
            chunk = self._buffer[:flush_index].strip()
            self._buffer = self._buffer[flush_index:]
            if chunk:
                chunks.append(chunk)

        return chunks

    def flush_remaining(self) -> str:
        """Flush and clear any remaining buffered text."""

        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining

    def _find_flush_index(self, text: str) -> int:
        if len(text) < self._min_chars:
            return 0

        punctuation_marks = [".", "!", "?", "\n", ";", ":"]
        best_match = -1
        for mark in punctuation_marks:
            idx = text.rfind(mark)
            if idx > best_match:
                best_match = idx

        if best_match >= self._min_chars - 1:
            return best_match + 1

        if len(text) >= self._max_chars:
            return self._max_chars

        return 0


class VoiceConversationOrchestrator:
    """Stateful orchestrator for one websocket-bound voice conversation."""

    def __init__(
        self,
        *,
        session_id: str,
        user_id: int,
        emit_event: EventEmitter,
        chat_session_id: int | None = None,
        launch_mode: str = "general",
        content_context: str | None = None,
        sample_rate_hz: int = 16_000,
    ) -> None:
        self.session_id = session_id
        self.user_id = user_id
        self.sample_rate_hz = sample_rate_hz
        self.chat_session_id = chat_session_id
        self.launch_mode = launch_mode
        self.content_context = content_context
        self._emit_event = emit_event
        self._stt_connection = None
        self._stt_partial_queue: asyncio.Queue[str] = asyncio.Queue()
        self._stt_final_queue: asyncio.Queue[tuple[float, str]] = asyncio.Queue()
        self._stt_error_queue: asyncio.Queue[str] = asyncio.Queue()
        self._last_partial_text = ""
        self._pending_audio_frames = 0
        self._pending_audio_bytes = 0
        self._audio_diag_frame_counter = 0
        self._pending_assistant_carryover = ""

    def _trace_enabled(self) -> bool:
        settings = get_settings()
        return bool(settings.voice_trace_logging)

    def _log_trace(self, operation: str, context_data: dict[str, Any]) -> None:
        if not self._trace_enabled():
            return
        logger.info(
            "Voice turn trace",
            extra={
                "component": "voice_orchestrator",
                "operation": operation,
                "item_id": self.user_id,
                "context_data": {"session_id": self.session_id, **context_data},
            },
        )

    async def start(self) -> None:
        """Start realtime STT connection for this session."""

        loop = asyncio.get_running_loop()

        def on_partial(text: str) -> None:
            if not text:
                return
            loop.call_soon_threadsafe(self._stt_partial_queue.put_nowait, text)

        def on_final(text: str) -> None:
            if not text:
                return
            loop.call_soon_threadsafe(self._stt_final_queue.put_nowait, (time.monotonic(), text))

        def on_error(message: str) -> None:
            loop.call_soon_threadsafe(self._stt_error_queue.put_nowait, message or "stt_error")

        self._stt_connection = await open_realtime_stt_connection(
            ElevenLabsSttCallbacks(
                on_partial=on_partial,
                on_final=on_final,
                on_error=on_error,
            ),
            sample_rate_hz=self.sample_rate_hz,
        )
        self._log_trace(
            "stt_started",
            {
                "sample_rate_hz": self.sample_rate_hz,
                "launch_mode": self.launch_mode,
            },
        )

    async def close(self) -> None:
        """Close external streaming resources."""

        await close_stt_connection(self._stt_connection)
        self._stt_connection = None
        self._log_trace(
            "stt_closed",
            {
                "pending_audio_frames": self._pending_audio_frames,
                "pending_audio_bytes": self._pending_audio_bytes,
            },
        )

    async def handle_audio_frame(self, pcm16_b64: str) -> None:
        """Forward one user audio frame to STT and emit transcript partials."""

        if self._stt_connection is None:
            raise RuntimeError("STT connection is not initialized")
        self._pending_audio_frames += 1
        self._audio_diag_frame_counter += 1
        self._pending_audio_bytes += max(0, (len(pcm16_b64) * 3) // 4)
        if self._pending_audio_frames == 1:
            self._log_trace(
                "audio_frame_first",
                {
                    "sample_rate_hz": self.sample_rate_hz,
                },
            )
        elif self._pending_audio_frames % 500 == 0:
            self._log_trace(
                "audio_frame_progress",
                {
                    "pending_audio_frames": self._pending_audio_frames,
                    "pending_audio_bytes": self._pending_audio_bytes,
                },
            )
        settings = get_settings()
        if (
            bool(settings.voice_audio_diag_logging)
            and self._trace_enabled()
            and (
                self._audio_diag_frame_counter == 1
                or self._audio_diag_frame_counter % 200 == 0
            )
        ):
            self._log_trace(
                "audio_frame_diagnostics",
                {
                    "sample_rate_hz": self.sample_rate_hz,
                    **self._summarize_pcm16_frame(pcm16_b64),
                },
            )
        await send_audio_frame(self._stt_connection, pcm16_b64)
        await self._emit_pending_stt_partials()
        await self._raise_pending_stt_errors()

    async def process_intro_turn(
        self,
        turn_id: str,
        intro_text: str,
        *,
        is_onboarding: bool = True,
    ) -> TurnOutcome:
        """Stream an intro turn through the normal text/audio channels.

        Args:
            turn_id: Correlation ID for this turn.
            intro_text: Pre-built greeting text to speak.
            is_onboarding: When True, emits ``is_intro: True`` so the client
                enters the ``intro.ack`` handshake flow. For returning-user
                greetings this should be False so the client treats the turn
                as a normal turn and auto-starts listening when it completes.
        """
        return await self._process_static_assistant_turn(
            turn_id=turn_id,
            assistant_text=intro_text,
            model_name="system:intro",
            is_intro=True,
            is_onboarding_intro=is_onboarding,
            persist_turn=False,
        )

    async def process_scripted_turn(
        self,
        turn_id: str,
        assistant_text: str,
        *,
        model: str = "system:scripted",
    ) -> TurnOutcome:
        """Stream a prebuilt assistant response without running STT or LLM."""

        return await self._process_static_assistant_turn(
            turn_id=turn_id,
            assistant_text=assistant_text,
            model_name=model,
            is_intro=False,
            is_onboarding_intro=False,
            persist_turn=True,
        )

    async def _process_static_assistant_turn(
        self,
        *,
        turn_id: str,
        assistant_text: str,
        model_name: str,
        is_intro: bool,
        is_onboarding_intro: bool,
        persist_turn: bool,
    ) -> TurnOutcome:
        """Emit one prepared assistant turn through text and TTS channels."""

        normalized_text = assistant_text.strip()
        if not normalized_text:
            return TurnOutcome(transcript="", assistant_text="", latency_ms=0)

        trace_operation = "intro_turn_started" if is_intro else "scripted_turn_started"
        self._log_trace(
            trace_operation,
            {
                "turn_id": turn_id,
                "assistant_chars": len(normalized_text),
                "is_intro": is_intro,
                "is_onboarding": is_onboarding_intro,
                "model_name": model_name,
            },
        )
        try:
            start_time = time.perf_counter()
            turn_started_event: dict[str, object] = {
                "type": "turn.started",
                "turn_id": turn_id,
            }
            if is_intro:
                turn_started_event["is_intro"] = True
                turn_started_event["is_onboarding_intro"] = is_onboarding_intro
            await self._emit_event(turn_started_event)
            await self._emit_event(
                {
                    "type": "assistant.text.delta",
                    "turn_id": turn_id,
                    "text": normalized_text,
                }
            )
            await self._emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": normalized_text,
                }
            )

            tts_enabled = await self._stream_text_to_tts(turn_id, normalized_text)
            if persist_turn:
                await self._persist_turn(transcript="", assistant_text=normalized_text)

            latency_ms = int((time.perf_counter() - start_time) * 1000)
            await self._emit_event(
                {
                    "type": "assistant.audio.final",
                    "turn_id": turn_id,
                    "tts_enabled": tts_enabled,
                }
            )
            await self._emit_event(
                {
                    "type": "turn.completed",
                    "turn_id": turn_id,
                    "latency_ms": latency_ms,
                    "transcript_chars": 0,
                    "response_chars": len(normalized_text),
                    "model": model_name,
                }
            )
            self._log_trace(
                "intro_turn_completed" if is_intro else "scripted_turn_completed",
                {
                    "turn_id": turn_id,
                    "latency_ms": latency_ms,
                    "tts_enabled": tts_enabled,
                    "model_name": model_name,
                },
            )
            return TurnOutcome(
                transcript="",
                assistant_text=normalized_text,
                latency_ms=latency_ms,
            )
        except asyncio.CancelledError:
            await self._emit_event(
                {
                    "type": "turn.cancelled",
                    "turn_id": turn_id,
                    "reason": "client_cancelled",
                }
            )
            self._log_trace(
                "intro_turn_cancelled" if is_intro else "scripted_turn_cancelled",
                {"turn_id": turn_id},
            )
            raise

    async def process_turn(self, turn_id: str) -> TurnOutcome:
        """Commit STT buffer, run LLM stream, and synthesize streaming TTS.

        Args:
            turn_id: Correlation ID for this turn.

        Returns:
            Final turn metrics and content.
        """

        start_time = time.perf_counter()
        await self._clear_stt_queue(self._stt_final_queue)
        await self._clear_stt_queue(self._stt_partial_queue)
        self._last_partial_text = ""
        await self._emit_event({"type": "turn.started", "turn_id": turn_id})
        self._log_trace(
            "turn_started_audio",
            {
                "turn_id": turn_id,
                "pending_audio_frames": self._pending_audio_frames,
                "pending_audio_bytes": self._pending_audio_bytes,
            },
        )

        transcript = await self._commit_and_collect_transcript(turn_id=turn_id)
        self._pending_audio_frames = 0
        self._pending_audio_bytes = 0
        if not transcript:
            self._log_trace(
                "turn_transcript_empty",
                {"turn_id": turn_id},
            )
            await self._emit_event(
                {
                    "type": "error",
                    "turn_id": turn_id,
                    "code": "empty_transcript",
                    "message": "No speech detected for this turn.",
                    "retryable": True,
                }
            )
            return TurnOutcome(transcript="", assistant_text="", latency_ms=0)

        await self._emit_event(
            {
                "type": "transcript.final",
                "turn_id": turn_id,
                "text": transcript,
            }
        )
        self._log_trace(
            "turn_transcript_final",
            {
                "turn_id": turn_id,
                "transcript_chars": len(transcript),
                "transcript_preview": _truncate_for_trace(transcript),
            },
        )

        return await self._run_agent_turn(
            turn_id=turn_id,
            transcript=transcript,
            start_time=start_time,
            assistant_carryover=self._consume_next_turn_carryover(),
        )

    async def process_text_turn(self, turn_id: str, user_text: str) -> TurnOutcome:
        """Run one streamed LLM/TTS turn for a text prompt without STT audio."""

        transcript = user_text.strip()
        if not transcript:
            await self._emit_event(
                {
                    "type": "error",
                    "turn_id": turn_id,
                    "code": "empty_text_turn",
                    "message": "No text was provided for this turn.",
                    "retryable": True,
                }
            )
            return TurnOutcome(transcript="", assistant_text="", latency_ms=0)

        self._log_trace(
            "turn_started_text",
            {
                "turn_id": turn_id,
                "transcript_chars": len(transcript),
                "transcript_preview": _truncate_for_trace(transcript),
            },
        )
        start_time = time.perf_counter()
        await self._emit_event({"type": "turn.started", "turn_id": turn_id})
        await self._emit_event(
            {
                "type": "transcript.final",
                "turn_id": turn_id,
                "text": transcript,
            }
        )

        return await self._run_agent_turn(
            turn_id=turn_id,
            transcript=transcript,
            start_time=start_time,
            assistant_carryover=self._consume_next_turn_carryover(),
        )

    async def _run_agent_turn(
        self,
        *,
        turn_id: str,
        transcript: str,
        start_time: float,
        assistant_carryover: str | None = None,
    ) -> TurnOutcome:
        """Execute one agent+TTS turn for a prepared transcript."""

        settings = get_settings()

        text_queue: queue.Queue[str | None] = queue.Queue()
        speech_chunker = _SpeechChunker()
        max_tts_chars = max(200, int(settings.voice_max_assistant_chars))
        tts_chars_sent = 0
        tts_task: asyncio.Task[int] | None = None
        tts_chunk_count = 0
        self._log_trace(
            "agent_turn_started",
            {
                "turn_id": turn_id,
                "transcript_chars": len(transcript),
                "transcript_preview": _truncate_for_trace(transcript),
                "max_tts_chars": max_tts_chars,
            },
        )

        try:
            audio_iterator = await asyncio.to_thread(
                build_realtime_tts_stream,
                self._queue_text_iterator(text_queue),
                voice_id=settings.elevenlabs_tts_voice_id,
                model_id=settings.elevenlabs_tts_model,
                output_format=settings.elevenlabs_tts_output_format,
            )
            tts_task = asyncio.create_task(self._pump_tts_audio(turn_id, audio_iterator))
            self._log_trace("tts_stream_ready", {"turn_id": turn_id})
        except Exception as exc:
            logger.error(
                "Voice TTS setup failed",
                extra={
                    "component": "voice_orchestrator",
                    "operation": "tts_setup",
                    "item_id": self.user_id,
                    "context_data": {"turn_id": turn_id, "error": str(exc)},
                },
            )
            await self._emit_event(
                {
                    "type": "error",
                    "turn_id": turn_id,
                    "code": "tts_unavailable",
                    "message": str(exc),
                    "retryable": True,
                }
            )

        async def on_text_delta(text_delta: str) -> None:
            nonlocal tts_chars_sent
            await self._emit_event(
                {
                    "type": "assistant.text.delta",
                    "turn_id": turn_id,
                    "text": text_delta,
                }
            )
            for chunk in speech_chunker.add_delta(text_delta):
                if tts_task is None or tts_chars_sent >= max_tts_chars:
                    continue
                remaining = max_tts_chars - tts_chars_sent
                bounded_chunk = chunk[:remaining]
                if not bounded_chunk:
                    continue
                tts_chars_sent += len(bounded_chunk)
                text_queue.put(bounded_chunk)

        try:
            history = get_message_history(self.session_id, self.user_id)
            agent_result = await stream_voice_agent_turn(
                user_id=self.user_id,
                user_text=transcript,
                message_history=history,
                on_text_delta=on_text_delta,
                content_context=self.content_context,
                launch_mode=self.launch_mode,
                assistant_carryover=assistant_carryover,
            )
            remaining_text = speech_chunker.flush_remaining()
            if remaining_text and tts_task is not None and tts_chars_sent < max_tts_chars:
                remaining = max_tts_chars - tts_chars_sent
                bounded_remaining = remaining_text[:remaining]
                if bounded_remaining:
                    text_queue.put(bounded_remaining)
            if tts_task is not None:
                text_queue.put(None)
                tts_chunk_count = await tts_task

            append_message_history(
                self.session_id,
                self.user_id,
                agent_result.new_messages,
            )
            await self._persist_turn(
                transcript=transcript,
                assistant_text=agent_result.assistant_text,
            )
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            await self._emit_event(
                {
                    "type": "assistant.text.final",
                    "turn_id": turn_id,
                    "text": agent_result.assistant_text,
                }
            )
            await self._emit_event(
                {
                    "type": "assistant.audio.final",
                    "turn_id": turn_id,
                    "tts_enabled": tts_task is not None,
                }
            )
            await self._emit_event(
                {
                    "type": "turn.completed",
                    "turn_id": turn_id,
                    "latency_ms": latency_ms,
                    "transcript_chars": len(transcript),
                    "response_chars": len(agent_result.assistant_text),
                    "model": agent_result.model_spec,
                }
            )
            self._log_trace(
                "agent_turn_completed",
                {
                    "turn_id": turn_id,
                    "latency_ms": latency_ms,
                    "transcript_chars": len(transcript),
                    "assistant_chars": len(agent_result.assistant_text),
                    "assistant_preview": _truncate_for_trace(agent_result.assistant_text),
                    "tts_enabled": tts_task is not None,
                    "tts_chars_sent": tts_chars_sent,
                    "tts_chunk_count": tts_chunk_count,
                    "model_spec": agent_result.model_spec,
                },
            )
            return TurnOutcome(
                transcript=transcript,
                assistant_text=agent_result.assistant_text,
                latency_ms=latency_ms,
            )
        except asyncio.CancelledError:
            if tts_task is not None:
                with suppress(queue.Full):
                    text_queue.put_nowait(None)
                tts_task.cancel()
                with suppress(Exception):
                    await tts_task
            await self._emit_event(
                {
                    "type": "turn.cancelled",
                    "turn_id": turn_id,
                    "reason": "barge_in",
                }
            )
            self._log_trace("agent_turn_cancelled", {"turn_id": turn_id})
            raise
        except Exception as exc:
            logger.exception(
                "Voice turn failed",
                extra={
                    "component": "voice_orchestrator",
                    "operation": "process_turn",
                    "item_id": self.user_id,
                    "context_data": {"turn_id": turn_id},
                },
            )
            if tts_task is not None:
                with suppress(queue.Full):
                    text_queue.put_nowait(None)
                tts_task.cancel()
                with suppress(Exception):
                    await tts_task
            await self._emit_event(
                {
                    "type": "error",
                    "turn_id": turn_id,
                    "code": "turn_failed",
                    "message": str(exc),
                    "retryable": True,
                }
            )
            raise

    async def _stream_text_to_tts(self, turn_id: str, text: str) -> bool:
        """Stream one complete text value through realtime TTS events."""

        settings = get_settings()
        text_queue: queue.Queue[str | None] = queue.Queue()
        speech_chunker = _SpeechChunker()
        max_tts_chars = max(200, int(settings.voice_max_assistant_chars))
        tts_chars_sent = 0
        self._log_trace(
            "intro_tts_started",
            {
                "turn_id": turn_id,
                "assistant_chars": len(text),
                "max_tts_chars": max_tts_chars,
            },
        )

        try:
            audio_iterator = await asyncio.to_thread(
                build_realtime_tts_stream,
                self._queue_text_iterator(text_queue),
                voice_id=settings.elevenlabs_tts_voice_id,
                model_id=settings.elevenlabs_tts_model,
                output_format=settings.elevenlabs_tts_output_format,
            )
        except Exception as exc:
            logger.error(
                "Voice intro TTS setup failed",
                extra={
                    "component": "voice_orchestrator",
                    "operation": "tts_setup_intro",
                    "item_id": self.user_id,
                    "context_data": {"turn_id": turn_id, "error": str(exc)},
                },
            )
            await self._emit_event(
                {
                    "type": "error",
                    "turn_id": turn_id,
                    "code": "tts_unavailable",
                    "message": str(exc),
                    "retryable": True,
                }
            )
            return False

        tts_task = asyncio.create_task(self._pump_tts_audio(turn_id, audio_iterator))
        try:
            for chunk in speech_chunker.add_delta(text):
                if tts_chars_sent >= max_tts_chars:
                    break
                remaining = max_tts_chars - tts_chars_sent
                bounded_chunk = chunk[:remaining]
                if not bounded_chunk:
                    continue
                tts_chars_sent += len(bounded_chunk)
                text_queue.put(bounded_chunk)

            remaining_text = speech_chunker.flush_remaining()
            if remaining_text and tts_chars_sent < max_tts_chars:
                remaining = max_tts_chars - tts_chars_sent
                bounded_remaining = remaining_text[:remaining]
                if bounded_remaining:
                    text_queue.put(bounded_remaining)

            text_queue.put(None)
            tts_chunk_count = await tts_task
            self._log_trace(
                "intro_tts_completed",
                {
                    "turn_id": turn_id,
                    "tts_chars_sent": tts_chars_sent,
                    "tts_chunk_count": tts_chunk_count,
                },
            )
            return True
        except asyncio.CancelledError:
            with suppress(queue.Full):
                text_queue.put_nowait(None)
            tts_task.cancel()
            with suppress(Exception):
                await tts_task
            raise

    async def _persist_turn(self, *, transcript: str, assistant_text: str) -> None:
        """Persist completed turn into chat tables when session mapping exists."""

        if self.chat_session_id is None:
            return
        if not transcript.strip() and not assistant_text.strip():
            return

        try:
            with get_db() as db:
                persist_voice_turn(
                    db,
                    user_id=self.user_id,
                    chat_session_id=self.chat_session_id,
                    transcript=transcript,
                    assistant_text=assistant_text,
                )
        except Exception:
            logger.exception(
                "Voice turn persistence failed",
                extra={
                    "component": "voice_orchestrator",
                    "operation": "persist_turn",
                    "item_id": self.user_id,
                    "context_data": {
                        "session_id": self.session_id,
                        "chat_session_id": self.chat_session_id,
                    },
                },
            )

    async def _commit_and_collect_transcript(self, *, turn_id: str) -> str:
        if self._stt_connection is None:
            raise RuntimeError("STT connection is not initialized")

        settings = get_settings()
        commit_timeout = max(1, int(settings.voice_stt_commit_timeout_seconds))
        self._log_trace(
            "stt_commit_sent",
            {
                "turn_id": turn_id,
                "commit_timeout_seconds": commit_timeout,
                "pending_audio_frames": self._pending_audio_frames,
                "pending_audio_bytes": self._pending_audio_bytes,
            },
        )
        commit_sent_at = time.monotonic()
        await commit_audio(self._stt_connection)
        deadline = time.monotonic() + commit_timeout

        while time.monotonic() < deadline:
            await self._emit_pending_stt_partials(turn_id=turn_id)
            await self._raise_pending_stt_errors()

            timeout = min(0.25, max(0.05, deadline - time.monotonic()))
            try:
                transcript_received_at, transcript = await asyncio.wait_for(
                    self._stt_final_queue.get(),
                    timeout=timeout,
                )
            except TimeoutError:
                continue

            if transcript_received_at + STT_FINAL_STALE_TOLERANCE_SECONDS < commit_sent_at:
                self._log_trace(
                    "stt_commit_result_ignored_stale",
                    {
                        "turn_id": turn_id,
                        "commit_sent_at": round(commit_sent_at, 6),
                        "transcript_received_at": round(transcript_received_at, 6),
                    },
                )
                continue

            text = transcript.strip()
            if text:
                self._log_trace(
                    "stt_commit_result",
                    {
                        "turn_id": turn_id,
                        "transcript_chars": len(text),
                        "transcript_preview": _truncate_for_trace(text),
                    },
                )
                return text

        self._log_trace(
            "stt_commit_timeout",
            {"turn_id": turn_id, "commit_timeout_seconds": commit_timeout},
        )
        return ""

    async def _emit_pending_stt_partials(self, turn_id: str | None = None) -> None:
        while True:
            try:
                partial_text = self._stt_partial_queue.get_nowait().strip()
            except asyncio.QueueEmpty:
                break
            if not partial_text or partial_text == self._last_partial_text:
                continue
            self._last_partial_text = partial_text
            payload: dict[str, Any] = {"type": "transcript.partial", "text": partial_text}
            if turn_id:
                payload["turn_id"] = turn_id
            await self._emit_event(payload)

    async def _raise_pending_stt_errors(self) -> None:
        try:
            error_message = self._stt_error_queue.get_nowait()
        except asyncio.QueueEmpty:
            return

        normalized_message = (error_message or "").strip().lower()
        is_commit_too_soon = (
            "commit request ignored" in normalized_message
            and "uncommitted audio" in normalized_message
        )
        if is_commit_too_soon:
            logger.info(
                "Ignoring recoverable STT commit-too-soon error",
                extra={
                    "component": "voice_orchestrator",
                    "operation": "stt_commit_ignored",
                    "item_id": self.user_id,
                    "context_data": {"session_id": self.session_id},
                },
            )
            return

        raise RuntimeError(f"STT error: {error_message}")

    async def _pump_tts_audio(self, turn_id: str, audio_iterator: Iterator[bytes]) -> int:
        seq = 0
        settings = get_settings()
        while True:
            audio_chunk = await next_tts_chunk(audio_iterator)
            if audio_chunk is None:
                return seq
            if not audio_chunk:
                continue
            await self._emit_event(
                {
                    "type": "assistant.audio.chunk",
                    "turn_id": turn_id,
                    "seq": seq,
                    "audio_b64": base64.b64encode(audio_chunk).decode("ascii"),
                    "format": settings.elevenlabs_tts_output_format,
                }
            )
            seq += 1

    async def _clear_stt_queue(self, target_queue: asyncio.Queue[Any]) -> None:
        while True:
            try:
                target_queue.get_nowait()
            except asyncio.QueueEmpty:
                return

    def set_next_turn_carryover(self, carryover_text: str) -> None:
        """Attach interrupted assistant context to the next agent turn."""

        normalized = carryover_text.strip()
        if not normalized:
            self._pending_assistant_carryover = ""
            return
        if len(normalized) > MAX_ASSISTANT_CARRYOVER_CHARS:
            normalized = normalized[-MAX_ASSISTANT_CARRYOVER_CHARS:]
        self._pending_assistant_carryover = normalized

    def _consume_next_turn_carryover(self) -> str | None:
        carryover = self._pending_assistant_carryover.strip()
        self._pending_assistant_carryover = ""
        if not carryover:
            return None
        return carryover

    def _queue_text_iterator(self, text_queue: queue.Queue[str | None]) -> Iterator[str]:
        while True:
            text_item = text_queue.get()
            if text_item is None:
                return
            if text_item:
                yield text_item

    def _summarize_pcm16_frame(self, pcm16_b64: str) -> dict[str, float | int]:
        """Compute compact diagnostics for one base64 PCM16 frame."""

        try:
            raw = base64.b64decode(pcm16_b64, validate=True)
        except Exception:
            return {"decode_error": 1}

        if len(raw) < 2:
            return {"samples": 0}

        sample_count = len(raw) // 2
        if sample_count <= 0:
            return {"samples": 0}

        sum_squares = 0.0
        max_abs = 0
        zero_count = 0
        clipped_count = 0

        # Little-endian signed int16 PCM
        for index in range(0, sample_count * 2, 2):
            sample = int.from_bytes(raw[index : index + 2], "little", signed=True)
            sample_abs = abs(sample)
            if sample_abs == 0:
                zero_count += 1
            if sample_abs >= 32760:
                clipped_count += 1
            if sample_abs > max_abs:
                max_abs = sample_abs
            normalized = sample / 32768.0
            sum_squares += normalized * normalized

        rms = (sum_squares / sample_count) ** 0.5
        peak = max_abs / 32768.0
        return {
            "samples": sample_count,
            "rms": round(rms, 6),
            "peak": round(peak, 6),
            "zero_ratio": round(zero_count / sample_count, 6),
            "clipping_ratio": round(clipped_count / sample_count, 6),
        }
