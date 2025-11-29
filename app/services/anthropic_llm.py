"""Anthropic summarization via pydantic-ai."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import NewsSummary, StructuredSummary
from app.services.llm_summarization import SummarizationRequest, summarize_content

logger = get_logger(__name__)
settings = get_settings()

SUMMARY_MODEL_SPEC = "claude-haiku-4-5-20251001"


class AnthropicSummarizationService:
    """Anthropic-powered summarization using pydantic-ai."""

    def __init__(self) -> None:
        if not getattr(settings, "anthropic_api_key", None):
            raise ValueError("Anthropic API key is required for LLM service")
        self.model_spec = SUMMARY_MODEL_SPEC
        logger.info("Initialized Anthropic summarization service (pydantic-ai)")

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


def get_anthropic_summarization_service() -> AnthropicSummarizationService:
    """Get Anthropic summarization service instance."""
    return AnthropicSummarizationService()
