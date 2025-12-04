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


class MessageProcessingStatus(str, Enum):
    """Processing status for async chat messages."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatMessageDto(BaseModel):
    """Flattened chat message returned to clients."""

    id: int = Field(..., description="Unique message identifier")
    session_id: int = Field(..., description="Chat session ID")
    role: ChatMessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Timestamp when message was stored")
    status: MessageProcessingStatus = Field(
        default=MessageProcessingStatus.COMPLETED,
        description="Processing status for async messages",
    )
    error: str | None = Field(default=None, description="Error message if processing failed")


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
    has_pending_message: bool = Field(
        default=False,
        description="True if session has a message currently being processed",
    )


class ChatSessionDetailDto(BaseModel):
    """Chat session with message history."""

    session: ChatSessionSummaryDto
    messages: list[ChatMessageDto]


class SendMessageResponse(BaseModel):
    """Response after sending a chat message (async).

    Returns immediately with the user message and a message_id to poll for completion.
    """

    session_id: int
    user_message: ChatMessageDto = Field(..., description="The user's message")
    message_id: int = Field(..., description="ID to poll for assistant response")
    status: MessageProcessingStatus = Field(
        default=MessageProcessingStatus.PROCESSING,
        description="Current processing status",
    )


class MessageStatusResponse(BaseModel):
    """Response when polling for message completion status."""

    message_id: int
    status: MessageProcessingStatus
    assistant_message: ChatMessageDto | None = Field(
        default=None,
        description="Assistant response (present when status=completed)",
    )
    error: str | None = Field(default=None, description="Error message if status=failed")


class CreateChatSessionResponse(BaseModel):
    """Response wrapper for session creation."""

    session: ChatSessionSummaryDto
