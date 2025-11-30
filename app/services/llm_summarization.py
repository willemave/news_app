"""Shared summarization flow using pydantic-ai agents."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Tuple

from app.core.logging import get_logger
from app.models.metadata import ContentQuote, ContentType, NewsSummary, StructuredSummary
from app.services.llm_agents import get_summarization_agent
from app.services.llm_models import resolve_model
from app.services.llm_prompts import generate_summary_prompt
from app.utils.error_logger import GenericErrorLogger

logger = get_logger(__name__)
error_logger = GenericErrorLogger("llm_summarization")

MAX_CONTENT_LENGTH = 1_500_000


@dataclass
class SummarizationRequest:
    """Request payload for summarizing content."""

    content: str
    content_type: str | ContentType
    model_spec: str
    title: str | None = None
    max_bullet_points: int = 6
    max_quotes: int = 8
    content_id: str | int | None = None


def _finalize_summary(
    summary: StructuredSummary | NewsSummary, content_type: str | ContentType
) -> StructuredSummary | NewsSummary:
    """Apply lightweight cleanup to keep summaries consistent."""
    if isinstance(summary, StructuredSummary) and summary.quotes:
        filtered: list[ContentQuote] = [
            quote for quote in summary.quotes if len((quote.text or "").strip()) >= 10
        ]
        summary.quotes = filtered

    return summary


def _normalize_content_type(content_type: str | ContentType) -> str:
    return content_type.value if isinstance(content_type, ContentType) else str(content_type)


DEFAULT_SUMMARIZATION_MODELS: Dict[str, str] = {
    "news": "openai:gpt-5-mini",
    "news_digest": "openai:gpt-5-mini",
    "article": "anthropic:claude-haiku-4-5-20251001",
    "podcast": "anthropic:claude-haiku-4-5-20251001",
}

FALLBACK_SUMMARIZATION_MODEL = "google-gla:gemini-2.5-flash-lite-preview-06-17"


def _model_hint_from_spec(model_spec: str) -> Tuple[str, str]:
    if ":" in model_spec:
        provider_prefix, hint = model_spec.split(":", 1)
        return provider_prefix, hint
    return "", model_spec


@dataclass
class ContentSummarizer:
    """Shared summarizer that routes to the right model based on content type."""

    default_models: Dict[str, str] = field(default_factory=lambda: DEFAULT_SUMMARIZATION_MODELS)
    provider_hint: str | None = None
    model_hint: str | None = None
    _model_resolver: Callable[[str | None, str | None], Tuple[str, str]] = resolve_model

    def summarize(
        self,
        content: str,
        content_type: str | ContentType,
        *,
        title: str | None = None,
        max_bullet_points: int = 6,
        max_quotes: int = 8,
        content_id: str | int | None = None,
        provider_override: str | None = None,
        model_hint: str | None = None,
    ) -> StructuredSummary | NewsSummary | None:
        """Summarize arbitrary content with sensible defaults per content type."""
        normalized_type = _normalize_content_type(content_type)
        default_model_spec = self.default_models.get(
            normalized_type, self.default_models.get("article", FALLBACK_SUMMARIZATION_MODEL)
        )
        default_provider_hint, default_model_hint = _model_hint_from_spec(default_model_spec)

        provider_to_use = provider_override or self.provider_hint or default_provider_hint
        model_hint_to_use = model_hint or self.model_hint or default_model_hint

        _, model_spec = self._model_resolver(provider_to_use, model_hint_to_use)

        request = SummarizationRequest(
            content=content,
            content_type=normalized_type,
            model_spec=model_spec,
            title=title,
            max_bullet_points=max_bullet_points,
            max_quotes=max_quotes,
            content_id=content_id,
        )
        return summarize_content(request)

    def summarize_content(
        self,
        content: str,
        max_bullet_points: int = 6,
        max_quotes: int = 8,
        content_type: str | ContentType = "article",
        *,
        title: str | None = None,
        content_id: str | int | None = None,
        provider_override: str | None = None,
        model_hint: str | None = None,
    ) -> StructuredSummary | NewsSummary | None:
        """Compatibility wrapper mirroring legacy service API."""
        return self.summarize(
            content=content,
            content_type=content_type,
            title=title,
            max_bullet_points=max_bullet_points,
            max_quotes=max_quotes,
            content_id=content_id,
            provider_override=provider_override,
            model_hint=model_hint,
        )


_content_summarizer: ContentSummarizer | None = None


def get_content_summarizer() -> ContentSummarizer:
    """Return a shared ContentSummarizer instance."""
    global _content_summarizer
    if _content_summarizer is None:
        _content_summarizer = ContentSummarizer()
    return _content_summarizer


def summarize_content(request: SummarizationRequest) -> StructuredSummary | NewsSummary | None:
    """Generate a structured summary via pydantic-ai.

    Args:
        request: SummarizationRequest containing content, model spec, and limits.

    Returns:
        Parsed StructuredSummary or NewsSummary instance, or None on failure.
    """
    try:
        payload = (
            request.content.decode("utf-8", errors="ignore")
            if isinstance(request.content, bytes)
            else request.content
        )
        if not payload:
            logger.warning("Empty summarization payload provided")
            return None

        if len(payload) > MAX_CONTENT_LENGTH:
            logger.warning(
                "Content length %s exceeds max %s; truncating for summarization",
                len(payload),
                MAX_CONTENT_LENGTH,
            )
            payload = payload[:MAX_CONTENT_LENGTH] + "\n\n[Content truncated due to length]"

        content_type_value = (
            request.content_type.value if isinstance(request.content_type, ContentType) else str(request.content_type)
        )

        prompt_content_type = "news_digest" if content_type_value == "news" else content_type_value

        system_prompt, user_template = generate_summary_prompt(
            prompt_content_type, request.max_bullet_points, request.max_quotes
        )

        content_body = payload
        if request.title:
            content_body = f"Title: {request.title}\n\n{content_body}"

        user_message = user_template.format(content=content_body)
        agent = get_summarization_agent(request.model_spec, prompt_content_type, system_prompt)
        result = agent.run_sync(user_message)
        summary = result.data
        return _finalize_summary(summary, request.content_type)
    except Exception as error:  # noqa: BLE001
        item_id = str(request.content_id or "unknown")
        logger.error("Summarization failed for content %s: %s", item_id, error)
        error_logger.log_processing_error(
            item_id=item_id,
            error=error,
            operation="summarization",
            context={
                "model_spec": request.model_spec,
                "content_type": str(request.content_type),
            },
        )
        return None
