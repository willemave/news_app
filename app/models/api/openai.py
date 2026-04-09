"""API schemas for OpenAI-related endpoints."""

from pydantic import BaseModel


class AudioTranscriptionResponse(BaseModel):
    """Transcription payload returned for uploaded audio."""

    transcript: str
    language: str | None = None


class AudioTranscriptionHealthResponse(BaseModel):
    """Dependency readiness for uploaded-audio transcription."""

    available: bool
