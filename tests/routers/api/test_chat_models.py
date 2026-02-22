"""Tests for chat API models."""

from __future__ import annotations

from app.routers.api.chat_models import ChatMessageRole


def test_chat_message_role_includes_tool() -> None:
    """ChatMessageRole should accept tool messages."""
    assert ChatMessageRole("tool") is ChatMessageRole.TOOL
