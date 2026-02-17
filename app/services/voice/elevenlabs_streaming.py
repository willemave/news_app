"""ElevenLabs streaming helpers for realtime STT/TTS."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any

from app.core.logging import get_logger
from app.core.settings import get_settings

try:  # pragma: no cover - import availability covered by readiness checks
    from elevenlabs.client import ElevenLabs
    from elevenlabs.realtime.connection import RealtimeConnection, RealtimeEvents
    from elevenlabs.realtime.scribe import AudioFormat, CommitStrategy
except Exception:  # pragma: no cover - gracefully handled at runtime
    ElevenLabs = None  # type: ignore[assignment]
    RealtimeConnection = Any  # type: ignore[assignment]
    RealtimeEvents = Any  # type: ignore[assignment]
    AudioFormat = Any  # type: ignore[assignment]
    CommitStrategy = Any  # type: ignore[assignment]

logger = get_logger(__name__)


@dataclass
class ElevenLabsSttCallbacks:
    """Callbacks invoked from ElevenLabs realtime transcription events."""

    on_partial: Callable[[str], None]
    on_final: Callable[[str], None]
    on_error: Callable[[str], None]


def elevenlabs_sdk_available() -> bool:
    """Return whether the ElevenLabs SDK is importable."""

    return find_spec("elevenlabs") is not None


def build_voice_health_flags() -> dict[str, Any]:
    """Build readiness flags for voice endpoints."""

    settings = get_settings()
    sdk_available = elevenlabs_sdk_available()
    api_key_configured = bool(settings.elevenlabs_api_key)
    anthropic_configured = bool(settings.anthropic_api_key)
    exa_configured = bool(settings.exa_api_key)

    readiness_reasons: list[str] = []
    if not api_key_configured:
        readiness_reasons.append("missing_elevenlabs_api_key")
    if not sdk_available:
        readiness_reasons.append("missing_elevenlabs_sdk")
    if not anthropic_configured:
        readiness_reasons.append("missing_anthropic_api_key")

    return {
        "elevenlabs_api_configured": api_key_configured,
        "elevenlabs_package_available": sdk_available,
        "anthropic_api_configured": anthropic_configured,
        "exa_api_configured": exa_configured,
        "tts_voice_id": settings.elevenlabs_tts_voice_id,
        "tts_model_id": settings.elevenlabs_tts_model,
        "tts_output_format": settings.elevenlabs_tts_output_format,
        "stt_model_id": settings.elevenlabs_stt_model_id,
        "ready": len(readiness_reasons) == 0,
        "readiness_reasons": readiness_reasons,
    }


def _ensure_elevenlabs_ready() -> None:
    """Validate ElevenLabs configuration and SDK availability."""

    settings = get_settings()
    if not settings.elevenlabs_api_key:
        raise RuntimeError("ElevenLabs API key is not configured")
    if not elevenlabs_sdk_available() or ElevenLabs is None:
        raise RuntimeError("ElevenLabs SDK is not installed")


def _resolve_audio_format(sample_rate_hz: int) -> Any:
    """Map sample rate to ElevenLabs realtime audio format enum."""

    if sample_rate_hz <= 8_000:
        return AudioFormat.PCM_8000
    if sample_rate_hz <= 16_000:
        return AudioFormat.PCM_16000
    if sample_rate_hz <= 22_050:
        return AudioFormat.PCM_22050
    if sample_rate_hz <= 24_000:
        return AudioFormat.PCM_24000
    if sample_rate_hz <= 44_100:
        return AudioFormat.PCM_44100
    return AudioFormat.PCM_48000


def _normalize_optional_language_code(language_code: str | None) -> str | None:
    """Normalize optional language code, treating blank strings as unset."""

    if language_code is None:
        return None
    normalized = language_code.strip()
    if not normalized:
        return None
    return normalized


async def open_realtime_stt_connection(
    callbacks: ElevenLabsSttCallbacks,
    sample_rate_hz: int = 16_000,
) -> RealtimeConnection:
    """Open ElevenLabs realtime STT connection and attach event handlers.

    Args:
        callbacks: Consumer callbacks for partial/final/error events.
        sample_rate_hz: Incoming client audio sample rate.

    Returns:
        Connected realtime transcription object.
    """

    _ensure_elevenlabs_ready()
    settings = get_settings()
    language_code = _normalize_optional_language_code(settings.elevenlabs_stt_language)
    if settings.voice_trace_logging:
        logger.info(
            "Opening ElevenLabs realtime STT connection",
            extra={
                "component": "voice_stt",
                "operation": "connect",
                "context_data": {
                    "model_id": settings.elevenlabs_stt_model_id,
                    "sample_rate_hz": sample_rate_hz,
                    "language_code": language_code,
                },
            },
        )
    client = ElevenLabs(api_key=settings.elevenlabs_api_key)
    connect_options: dict[str, Any] = {
        "model_id": settings.elevenlabs_stt_model_id,
        "audio_format": _resolve_audio_format(sample_rate_hz),
        "sample_rate": sample_rate_hz,
        "commit_strategy": CommitStrategy.MANUAL,
    }
    if language_code is not None:
        connect_options["language_code"] = language_code

    connection: RealtimeConnection = await client.speech_to_text.realtime.connect(connect_options)

    def _extract_transcript(payload: dict[str, Any]) -> str:
        """Extract transcript text across realtime payload variants."""

        transcript = payload.get("transcript")
        if transcript is None:
            transcript = payload.get("text")
        if transcript is None:
            transcript = payload.get("transcript_text")
        if transcript is None:
            return ""
        return str(transcript).strip()

    connection.on(
        RealtimeEvents.PARTIAL_TRANSCRIPT,
        lambda payload: callbacks.on_partial(_extract_transcript(payload)),
    )
    connection.on(
        RealtimeEvents.COMMITTED_TRANSCRIPT,
        lambda payload: callbacks.on_final(_extract_transcript(payload)),
    )
    connection.on(
        RealtimeEvents.COMMITTED_TRANSCRIPT_WITH_TIMESTAMPS,
        lambda payload: callbacks.on_final(_extract_transcript(payload)),
    )
    connection.on(
        RealtimeEvents.ERROR,
        lambda payload: callbacks.on_error(str(payload.get("error", "stt_error"))),
    )
    return connection


async def send_audio_frame(connection: RealtimeConnection, audio_bytes_b64: str) -> None:
    """Send one base64 audio frame to ElevenLabs realtime STT."""

    await connection.send({"audio_base_64": audio_bytes_b64})


async def commit_audio(connection: RealtimeConnection) -> None:
    """Commit current STT buffer and request final transcript."""

    await connection.commit()


async def close_stt_connection(connection: RealtimeConnection | None) -> None:
    """Close realtime STT connection safely."""

    if connection is None:
        return
    await connection.close()


def build_realtime_tts_stream(
    text_iterator: Iterator[str],
    *,
    voice_id: str | None = None,
    model_id: str | None = None,
    output_format: str | None = None,
) -> Iterator[bytes]:
    """Create realtime TTS audio iterator from text fragments.

    Args:
        text_iterator: Iterator yielding text fragments as they become available.
        voice_id: Optional voice override.
        model_id: Optional model override.
        output_format: Optional output format override.

    Returns:
        Iterator of raw audio bytes from ElevenLabs.
    """

    _ensure_elevenlabs_ready()
    settings = get_settings()
    client = ElevenLabs(api_key=settings.elevenlabs_api_key)

    effective_voice_id = voice_id or settings.elevenlabs_tts_voice_id
    if not effective_voice_id:
        raise RuntimeError("ElevenLabs TTS voice_id is not configured")
    if settings.voice_trace_logging:
        logger.info(
            "Opening ElevenLabs realtime TTS stream",
            extra={
                "component": "voice_tts",
                "operation": "connect",
                "context_data": {
                    "voice_id": effective_voice_id,
                    "model_id": model_id or settings.elevenlabs_tts_model,
                    "output_format": output_format or settings.elevenlabs_tts_output_format,
                },
            },
        )

    return client.text_to_speech.convert_realtime(
        voice_id=effective_voice_id,
        text=text_iterator,
        model_id=model_id or settings.elevenlabs_tts_model,
        output_format=output_format or settings.elevenlabs_tts_output_format,
        voice_settings=None,
    )


async def next_tts_chunk(audio_iterator: Iterator[bytes]) -> bytes | None:
    """Return next TTS chunk from a blocking iterator via thread offload."""

    def _next_chunk() -> bytes | None:
        try:
            return next(audio_iterator)
        except StopIteration:
            return None

    return await asyncio.to_thread(_next_chunk)
