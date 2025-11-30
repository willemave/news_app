"""Google Gemini summarization via pydantic-ai."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.llm_summarization import ContentSummarizer, get_content_summarizer

logger = get_logger(__name__)
settings = get_settings()

SUMMARY_MODEL_SPEC = "gemini-2.5-flash-lite-preview-06-17"


class GoogleFlashService(ContentSummarizer):
    """Google Gemini service for content summarization."""

    def __init__(self) -> None:
        if not getattr(settings, "google_api_key", None):
            raise ValueError("Google API key is required for LLM service")
        super().__init__(provider_hint="google", model_hint=SUMMARY_MODEL_SPEC)
        logger.info("Initialized Google Gemini provider for summarization (pydantic-ai)")


_google_flash_service: GoogleFlashService | None = None


def get_google_flash_service() -> GoogleFlashService:
    """Get the global Google Flash service instance."""
    global _google_flash_service
    if _google_flash_service is None:
        _google_flash_service = GoogleFlashService()
        _google_flash_service.default_models = get_content_summarizer().default_models
    return _google_flash_service
