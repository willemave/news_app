"""Chat DTOs for API responses."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.services.llm_models import LLMProvider as ChatModelProvider


class ChatMessageRole(str, Enum):
    """Role of a chat message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class MessageProcessingStatus(str, Enum):
    """Processing status for async chat messages."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class CreateChatSessionRequest(BaseModel):
    """Request to create a new chat session."""

    content_id: int | None = Field(None, description="Content ID to chat about")
    topic: str | None = Field(None, max_length=500, description="Specific topic to discuss")
    llm_provider: ChatModelProvider | None = Field(
        None, description="LLM provider (defaults to anthropic)"
    )
    llm_model_hint: str | None = Field(
        None, max_length=100, description="Optional specific model to use"
    )
    initial_message: str | None = Field(
        None, max_length=2000, description="Optional initial user message"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "content_id": 123,
                "topic": None,
                "llm_provider": "anthropic",
                "llm_model_hint": None,
                "initial_message": "What are the key insights from this article?",
            }
        }


class UpdateChatSessionRequest(BaseModel):
    """Request to update a chat session."""

    llm_provider: ChatModelProvider | None = Field(
        None, description="New LLM provider to use for this session"
    )
    llm_model_hint: str | None = Field(
        None, max_length=100, description="Optional specific model to use"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "llm_provider": "anthropic",
                "llm_model_hint": None,
            }
        }


class SendChatMessageRequest(BaseModel):
    """Request to send a message in a chat session."""

    message: str = Field(..., min_length=1, max_length=10000, description="Message to send")

    class Config:
        json_schema_extra = {"example": {"message": "Can you explain that in more detail?"}}


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
    article_summary: str | None = Field(
        default=None,
        description="Short summary of the article (for empty session display)",
    )
    article_source: str | None = Field(
        default=None,
        description="Source name of the article (for empty session display)",
    )
    has_pending_message: bool = Field(
        default=False,
        description="True if session has a message currently being processed",
    )
    is_favorite: bool = Field(
        default=False,
        description="True if the linked content is favorited by the user",
    )
    has_messages: bool = Field(
        default=True,
        description="True if session has any messages (false for new favorites)",
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
