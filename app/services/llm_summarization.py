"""Shared summarization flow using pydantic-ai agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger
from app.models.metadata import ContentQuote, ContentType, NewsSummary, StructuredSummary
from app.services.llm_agents import get_summarization_agent
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
