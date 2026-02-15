"""Pydantic DTOs for voice session endpoints and websocket events."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter


class CreateVoiceSessionRequest(BaseModel):
    """Request payload for creating or resuming a voice session."""

    session_id: str | None = Field(
        default=None,
        description="Optional existing session ID for reconnect/resume.",
        max_length=128,
    )
    sample_rate_hz: int = Field(
        default=16_000,
        ge=8_000,
        le=48_000,
        description="Client microphone sample rate.",
    )
    content_id: int | None = Field(
        default=None,
        ge=1,
        description="Optional content item for contextual live voice.",
    )
    chat_session_id: int | None = Field(
        default=None,
        ge=1,
        description="Optional existing chat session ID for live continuation.",
    )
    launch_mode: Literal["general", "article_voice", "dictate_summary"] = Field(
        default="general",
        description="Voice entrypoint mode.",
    )
    source_surface: Literal["knowledge_live", "chat_session", "content_detail"] = Field(
        default="knowledge_live",
        description="Client surface that launched live voice.",
    )
    request_intro: bool = Field(
        default=False,
        description="Request first-use intro turn when user has not completed onboarding.",
    )


class CreateVoiceSessionResponse(BaseModel):
    """Session metadata required to open websocket streaming."""

    session_id: str
    websocket_path: str
    sample_rate_hz: int
    channels: int = 1
    audio_format: str = "pcm16"
    tts_output_format: str
    max_input_seconds: int
    chat_session_id: int
    launch_mode: Literal["general", "article_voice", "dictate_summary"]
    content_context_attached: bool


class VoiceHealthResponse(BaseModel):
    """Capabilities and readiness for voice pipeline dependencies."""

    ready: bool
    elevenlabs_api_configured: bool
    elevenlabs_package_available: bool
    anthropic_api_configured: bool
    exa_api_configured: bool
    stt_model_id: str
    tts_voice_id: str | None
    tts_model_id: str | None
    tts_output_format: str | None
    readiness_reasons: list[str]


class VoiceClientSessionStartEvent(BaseModel):
    """Client event indicating websocket session initialization."""

    type: Literal["session.start"]
    session_id: str


class VoiceClientAudioFrameEvent(BaseModel):
    """Client event containing one microphone frame."""

    type: Literal["audio.frame"]
    seq: int = Field(ge=0)
    pcm16_b64: str = Field(min_length=1)
    sample_rate_hz: int = Field(default=16_000, ge=8_000, le=48_000)
    channels: int = Field(default=1, ge=1, le=2)


class VoiceClientAudioCommitEvent(BaseModel):
    """Client event marking end-of-utterance for transcription commit."""

    type: Literal["audio.commit"]
    seq: int | None = Field(default=None, ge=0)


class VoiceClientCancelEvent(BaseModel):
    """Client event requesting cancellation of current assistant response."""

    type: Literal["response.cancel"]
    reason: str | None = Field(default=None, max_length=120)


class VoiceClientSessionEndEvent(BaseModel):
    """Client event for intentional websocket session shutdown."""

    type: Literal["session.end"]


class VoiceClientIntroAckEvent(BaseModel):
    """Client event acknowledging first-use intro playback completion."""

    type: Literal["intro.ack"]


VoiceClientEvent = Annotated[
    VoiceClientSessionStartEvent
    | VoiceClientAudioFrameEvent
    | VoiceClientAudioCommitEvent
    | VoiceClientCancelEvent
    | VoiceClientSessionEndEvent
    | VoiceClientIntroAckEvent,
    Field(discriminator="type"),
]

VOICE_CLIENT_EVENT_ADAPTER = TypeAdapter(VoiceClientEvent)
