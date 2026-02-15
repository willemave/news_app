"""Tests for in-memory voice session management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.services.voice.session_manager import (
    append_message_history,
    clear_voice_sessions,
    configure_voice_session,
    create_voice_session,
    get_message_history,
    get_voice_session,
    prune_voice_sessions,
)


def test_create_and_get_voice_session() -> None:
    """Session can be created and retrieved by owning user."""

    clear_voice_sessions()
    state = create_voice_session(user_id=123)
    loaded = get_voice_session(session_id=state.session_id, user_id=123)

    assert loaded is not None
    assert loaded.session_id == state.session_id
    assert loaded.user_id == 123


def test_get_voice_session_rejects_other_user() -> None:
    """Session lookup should fail for non-owner user IDs."""

    clear_voice_sessions()
    state = create_voice_session(user_id=5)

    loaded = get_voice_session(session_id=state.session_id, user_id=6)
    assert loaded is None


def test_append_and_read_message_history() -> None:
    """Appending message history should be reflected in reads."""

    clear_voice_sessions()
    state = create_voice_session(user_id=7)
    append_message_history(
        session_id=state.session_id,
        user_id=7,
        messages=[object(), object()],  # runtime accepts model message objects
    )

    history = get_message_history(session_id=state.session_id, user_id=7)
    assert len(history) == 2


def test_prune_voice_sessions_removes_expired_entries() -> None:
    """Expired sessions should be removed by prune."""

    clear_voice_sessions()
    state = create_voice_session(user_id=9)
    assert get_voice_session(state.session_id, user_id=9) is not None

    loaded = get_voice_session(state.session_id, user_id=9)
    assert loaded is not None
    loaded.updated_at = datetime.now(UTC) - timedelta(minutes=10)

    prune_voice_sessions(ttl_minutes=1)
    assert get_voice_session(state.session_id, user_id=9) is None


def test_configure_voice_session_sets_launch_metadata() -> None:
    """Session metadata should be attached for live voice routing."""

    clear_voice_sessions()
    state = create_voice_session(user_id=10)
    configured = configure_voice_session(
        session_id=state.session_id,
        user_id=10,
        chat_session_id=321,
        content_id=44,
        launch_mode="article_voice",
        source_surface="content_detail",
        pending_intro=True,
        content_context="title: Example",
        content_title="Example",
    )

    assert configured is not None
    assert configured.chat_session_id == 321
    assert configured.content_id == 44
    assert configured.launch_mode == "article_voice"
    assert configured.pending_intro is True
