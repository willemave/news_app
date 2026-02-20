"""In-memory session manager for realtime voice conversations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import uuid4

from pydantic_ai.messages import ModelMessage

from app.core.settings import get_settings


@dataclass
class VoiceSessionState:
    """State for one realtime voice session."""

    session_id: str
    user_id: int
    chat_session_id: int | None = None
    content_id: int | None = None
    launch_mode: str = "general"
    source_surface: str = "knowledge_live"
    pending_intro: bool = False
    is_onboarding_intro: bool = False
    content_context: str | None = None
    content_title: str | None = None
    summary_narration: str | None = None
    message_history: list[ModelMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


_VOICE_SESSION_STORE: dict[str, VoiceSessionState] = {}
_VOICE_SESSION_LOCK = Lock()


def create_voice_session(user_id: int, session_id: str | None = None) -> VoiceSessionState:
    """Create a new voice session or return an existing one owned by the user.

    Args:
        user_id: Authenticated user identifier.
        session_id: Optional existing session identifier.

    Returns:
        Session state for the caller.

    Raises:
        ValueError: If a provided session exists but belongs to a different user.
    """

    prune_voice_sessions()
    normalized_session_id = (session_id or "").strip() or str(uuid4())
    now = datetime.now(UTC)

    with _VOICE_SESSION_LOCK:
        existing = _VOICE_SESSION_STORE.get(normalized_session_id)
        if existing is None:
            state = VoiceSessionState(
                session_id=normalized_session_id,
                user_id=user_id,
                created_at=now,
                updated_at=now,
            )
            _VOICE_SESSION_STORE[normalized_session_id] = state
            return state

        if existing.user_id != user_id:
            raise ValueError("session_id does not belong to authenticated user")

        existing.updated_at = now
        return existing


def configure_voice_session(
    *,
    session_id: str,
    user_id: int,
    chat_session_id: int,
    content_id: int | None,
    launch_mode: str,
    source_surface: str,
    pending_intro: bool,
    is_onboarding_intro: bool = False,
    content_context: str | None,
    content_title: str | None,
    summary_narration: str | None = None,
) -> VoiceSessionState | None:
    """Attach launch metadata to an in-memory voice session."""

    with _VOICE_SESSION_LOCK:
        state = _VOICE_SESSION_STORE.get(session_id)
        if state is None or state.user_id != user_id:
            return None
        state.chat_session_id = chat_session_id
        state.content_id = content_id
        state.launch_mode = launch_mode
        state.source_surface = source_surface
        state.pending_intro = pending_intro
        state.is_onboarding_intro = is_onboarding_intro
        state.content_context = content_context
        state.content_title = content_title
        state.summary_narration = summary_narration
        state.updated_at = datetime.now(UTC)
        return state


def set_voice_session_intro_pending(
    *,
    session_id: str,
    user_id: int,
    pending_intro: bool,
) -> None:
    """Update pending intro state for an in-memory session."""

    with _VOICE_SESSION_LOCK:
        state = _VOICE_SESSION_STORE.get(session_id)
        if state is None or state.user_id != user_id:
            return
        state.pending_intro = pending_intro
        state.updated_at = datetime.now(UTC)


def get_voice_session(session_id: str, user_id: int) -> VoiceSessionState | None:
    """Load an existing voice session for a specific user.

    Args:
        session_id: Session identifier.
        user_id: Authenticated user identifier.

    Returns:
        Session state when found and owned by the caller, otherwise ``None``.
    """

    with _VOICE_SESSION_LOCK:
        state = _VOICE_SESSION_STORE.get(session_id)
        if state is None or state.user_id != user_id:
            return None
        state.updated_at = datetime.now(UTC)
        return state


def get_message_history(session_id: str, user_id: int) -> list[ModelMessage]:
    """Return a copy of message history for one voice session.

    Args:
        session_id: Session identifier.
        user_id: Authenticated user identifier.

    Returns:
        Message history; empty list when the session is missing.
    """

    with _VOICE_SESSION_LOCK:
        state = _VOICE_SESSION_STORE.get(session_id)
        if state is None or state.user_id != user_id:
            return []
        state.updated_at = datetime.now(UTC)
        return list(state.message_history)


def append_message_history(session_id: str, user_id: int, messages: list[ModelMessage]) -> None:
    """Append new model messages to the session history.

    Args:
        session_id: Session identifier.
        user_id: Authenticated user identifier.
        messages: New model messages from the latest completed turn.
    """

    if not messages:
        return

    settings = get_settings()
    max_turns = max(1, int(settings.voice_max_context_turns))
    max_messages = max_turns * 2

    with _VOICE_SESSION_LOCK:
        state = _VOICE_SESSION_STORE.get(session_id)
        if state is None or state.user_id != user_id:
            return
        state.message_history.extend(messages)
        if len(state.message_history) > max_messages:
            state.message_history = state.message_history[-max_messages:]
        state.updated_at = datetime.now(UTC)


def prune_voice_sessions(ttl_minutes: int | None = None) -> None:
    """Remove expired voice sessions from memory.

    Args:
        ttl_minutes: Optional override for tests.
    """

    settings = get_settings()
    configured_ttl = ttl_minutes if ttl_minutes is not None else settings.voice_session_ttl_minutes
    effective_ttl = max(1, int(configured_ttl))
    cutoff = datetime.now(UTC) - timedelta(minutes=effective_ttl)

    with _VOICE_SESSION_LOCK:
        expired = [
            session_id
            for session_id, state in _VOICE_SESSION_STORE.items()
            if state.updated_at < cutoff
        ]
        for session_id in expired:
            _VOICE_SESSION_STORE.pop(session_id, None)


def clear_voice_sessions() -> None:
    """Clear all in-memory voice sessions (test helper)."""

    with _VOICE_SESSION_LOCK:
        _VOICE_SESSION_STORE.clear()
