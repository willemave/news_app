"""Pydantic models for admin conversational endpoints."""

from pydantic import BaseModel, Field


class AdminConversationalHealthResponse(BaseModel):
    """Readiness flags for admin conversational features."""

    elevenlabs_api_configured: bool = Field(..., description="Whether ELEVENLABS_API_KEY is set")
    elevenlabs_package_available: bool = Field(
        ..., description="Whether the elevenlabs SDK can be imported"
    )
    agent_id: str | None = Field(None, description="Configured ElevenLabs agent ID")
    agent_text_only: bool = Field(..., description="Whether text-only mode is requested")
    readiness_reasons: list[str] = Field(
        default_factory=list,
        description="Reasons why readiness is false.",
    )
    ready: bool = Field(..., description="Whether the conversational feature is ready")
