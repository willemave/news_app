"""Chat DTOs for API responses."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ChatMessageRole(str, Enum):
    """Role of a chat message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessageDto(BaseModel):
    """Flattened chat message returned to clients."""

    id: int = Field(..., description="Unique message identifier")
    session_id: int = Field(..., description="Chat session ID")
    role: ChatMessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Timestamp when message was stored")


class ChatSessionSummaryDto(BaseModel):
    """Summary of a chat session."""

    id: int
    title: str | None
    content_id: int | None
    session_type: str | None
    topic: str | None
    llm_model: str
    llm_provider: str
    created_at: datetime
    updated_at: datetime | None
    last_message_at: datetime | None
    is_archived: bool
    article_title: str | None = None
    article_url: str | None = None


class ChatSessionDetailDto(BaseModel):
    """Chat session with message history."""

    session: ChatSessionSummaryDto
    messages: list[ChatMessageDto]


class SendMessageResponse(BaseModel):
    """Response after sending a chat message."""

    session_id: int
    assistant_message: ChatMessageDto


class CreateChatSessionResponse(BaseModel):
    """Response wrapper for session creation."""

    session: ChatSessionSummaryDto
