"""Anthropic summarization via pydantic-ai."""

from __future__ import annotations

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.services.llm_summarization import ContentSummarizer, get_content_summarizer

logger = get_logger(__name__)
settings = get_settings()

SUMMARY_MODEL_SPEC = "claude-haiku-4-5-20251001"


class AnthropicSummarizationService(ContentSummarizer):
    """Anthropic-powered summarization using shared ContentSummarizer."""

    def __init__(self) -> None:
        if not getattr(settings, "anthropic_api_key", None):
            raise ValueError("Anthropic API key is required for LLM service")
        super().__init__(provider_hint="anthropic", model_hint=SUMMARY_MODEL_SPEC)
        logger.info("Initialized Anthropic summarization service (pydantic-ai)")


def get_anthropic_summarization_service() -> AnthropicSummarizationService:
    """Get Anthropic summarization service instance."""
    service = AnthropicSummarizationService()
    service.default_models = get_content_summarizer().default_models
    return service
