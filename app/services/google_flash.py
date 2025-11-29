"""Google Gemini summarization via pydantic-ai."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import NewsSummary, StructuredSummary
from app.services.llm_summarization import SummarizationRequest, summarize_content

logger = get_logger(__name__)
settings = get_settings()

SUMMARY_MODEL_SPEC = "gemini-2.5-flash-lite-preview-06-17"


class GoogleFlashService:
    """Google Gemini service for content summarization."""

    def __init__(self) -> None:
        if not getattr(settings, "google_api_key", None):
            raise ValueError("Google API key is required for LLM service")
        self.model_spec = SUMMARY_MODEL_SPEC
        logger.info("Initialized Google Gemini provider for summarization (pydantic-ai)")

    def summarize_content(
        self,
        content: str,
        max_bullet_points: int = 6,
        max_quotes: int = 8,
        content_type: str = "article",
    ) -> StructuredSummary | NewsSummary | None:
        """Summarize text content."""
        request = SummarizationRequest(
            content=content,
            content_type=content_type,
            model_spec=self.model_spec,
            max_bullet_points=max_bullet_points,
            max_quotes=max_quotes,
        )
        return summarize_content(request)


_google_flash_service: GoogleFlashService | None = None


def get_google_flash_service() -> GoogleFlashService:
    """Get the global Google Flash service instance."""
    global _google_flash_service
    if _google_flash_service is None:
        _google_flash_service = GoogleFlashService()
    return _google_flash_service
