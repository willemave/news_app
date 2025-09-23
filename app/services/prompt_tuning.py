"""Services for generating summarization prompt update suggestions."""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timedelta

from openai import OpenAI, OpenAIError
from pydantic import ValidationError
from sqlalchemy import Select, desc, select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.domain.converters import content_to_domain
from app.models.schema import Content, ContentUnlikes
from app.schemas.prompt_updates import (
    PromptExample,
    PromptUpdateRequest,
    PromptUpdateResult,
    PromptUpdateSuggestion,
)
from app.services.openai_llm import generate_summary_prompt, get_openai_summarization_service

logger = get_logger(__name__)


class PromptTuningError(Exception):
    """Raised when the prompt tuning workflow fails."""


def collect_unliked_examples(db: Session, request: PromptUpdateRequest) -> list[PromptExample]:
    """Fetch unliked content within the requested window and serialize for LLM input."""

    cutoff = datetime.utcnow() - timedelta(days=request.lookback_days)
    stmt: Select[tuple[Content, ContentUnlikes]] = (
        select(Content, ContentUnlikes)
        .join(ContentUnlikes, Content.id == ContentUnlikes.content_id)
        .where(ContentUnlikes.unliked_at >= cutoff)
        .order_by(desc(ContentUnlikes.unliked_at))
        .limit(request.max_examples)
    )

    rows = db.execute(stmt).all()
    examples: list[PromptExample] = []

    for content, unlike in rows:
        try:
            domain = content_to_domain(content)
        except Exception as exc:  # pragma: no cover - defensive safeguard
            logger.warning("Failed to convert content %s to domain model: %s", content.id, exc)
            continue

        summary_text = _truncate_text(domain.summary, 800)
        short_summary = _truncate_text(domain.short_summary, 320)
        topics = _clean_topics(domain.topics)
        bullet_points = _extract_bullet_points(domain.bullet_points)
        classification = None

        structured = domain.structured_summary or {}
        if isinstance(structured, dict):
            classification = structured.get("classification")

        examples.append(
            PromptExample(
                content_id=content.id,
                unliked_at=unlike.unliked_at,
                content_type=content.content_type,
                title=content.title or "Untitled",
                source=content.source,
                short_summary=short_summary,
                summary=summary_text,
                topics=topics,
                bullet_points=bullet_points,
                classification=classification,
            )
        )

    return examples


def build_prompt_update(
    request: PromptUpdateRequest,
    examples: Iterable[PromptExample],
    *,
    current_prompt_instructions: str | None = None,
) -> PromptUpdateSuggestion:
    """Generate a prompt update suggestion via the OpenAI model."""

    serialized_examples = [
        {
            "content_id": example.content_id,
            "unliked_at": example.unliked_at.isoformat(),
            "content_type": example.content_type,
            "title": example.title,
            "source": example.source,
            "short_summary": example.short_summary,
            "summary": example.summary,
            "topics": example.topics,
            "bullet_points": example.bullet_points,
            "classification": example.classification,
        }
        for example in examples
    ]

    if not serialized_examples:
        raise PromptTuningError("No unliked content found for the selected window.")

    prompt_instructions = (
        current_prompt_instructions or _fetch_current_article_prompt_instructions()
    )

    prompt_payload = _render_tuning_prompt(
        request=request,
        prompt_instructions=prompt_instructions,
        serialized_examples=serialized_examples,
    )

    service = get_openai_summarization_service()
    client: OpenAI = service.client
    model_name = service.model_name

    try:
        response = client.beta.chat.completions.parse(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert summarization prompt engineer who outputs valid JSON suggestions.",
                },
                {"role": "user", "content": prompt_payload},
            ],
            temperature=0.35,
            max_output_tokens=3500,
            response_format=PromptUpdateSuggestion,
        )

        if not response.choices:
            raise PromptTuningError("Model returned no choices.")

        parsed = getattr(response.choices[0].message, "parsed", None)
        if parsed is None:
            raise PromptTuningError("Model response missing parsed payload.")

        return parsed
    except (OpenAIError, ValidationError) as exc:
        logger.exception("Failed to parse prompt update suggestion: %s", exc)
        raise PromptTuningError("Model response could not be parsed as JSON.") from exc
    except Exception as exc:  # pragma: no cover - unanticipated errors logged
        logger.exception("Unexpected error while generating prompt update: %s", exc)
        raise PromptTuningError("Unexpected error while generating prompt update.") from exc


def generate_prompt_update_result(
    db: Session, request: PromptUpdateRequest, should_generate: bool
) -> PromptUpdateResult:
    """Orchestrate data collection and optional LLM generation for the web layer."""

    examples = collect_unliked_examples(db, request)
    suggestion: PromptUpdateSuggestion | None = None
    error_message: str | None = None

    if should_generate:
        try:
            suggestion = build_prompt_update(request, examples)
        except PromptTuningError as exc:
            error_message = str(exc)

    return PromptUpdateResult(
        request=request,
        examples=examples,
        suggestion=suggestion,
        error=error_message,
    )


def summarize_examples(examples: Iterable[PromptExample]) -> dict[str, list[tuple[str, int]]]:
    """Compute lightweight analytics from prompt examples for display."""

    sources = Counter()
    content_types = Counter()

    for example in examples:
        if example.source:
            sources[example.source] += 1
        content_types[example.content_type] += 1

    top_sources = sources.most_common(5)
    type_breakdown = content_types.most_common()

    return {
        "sources": top_sources,
        "content_types": type_breakdown,
    }


def _render_tuning_prompt(
    *,
    request: PromptUpdateRequest,
    prompt_instructions: str,
    serialized_examples: list[dict[str, object]],
) -> str:
    """Render the textual prompt sent to the LLM."""

    summary = {
        "lookback_days": request.lookback_days,
        "example_count": len(serialized_examples),
    }

    aggregate = summarize_examples(
        PromptExample.model_validate(example) for example in serialized_examples
    )

    payload = {
        "summary": summary,
        "aggregate": aggregate,
        "examples": serialized_examples,
    }

    return (
        "You are an expert prompt engineer tasked with improving a summarization prompt.\n"
        "Review the current summarization instructions and the set of unliked content summaries.\n"
        "Identify why these outputs were unsatisfactory and propose actionable updates.\n"
        "Respond with JSON containing the fields defined in the provided schema."\
        "\n\n"
        "Current summarization prompt instructions:\n"
        """<current_prompt>""" + prompt_instructions + """</current_prompt>\n\n"""
        "Historical unliked content dataset (JSON):\n"
        + json.dumps(payload, ensure_ascii=False, indent=2)
    )


def _fetch_current_article_prompt_instructions() -> str:
    """Extract the current article summarization instructions without the content payload."""

    template = generate_summary_prompt(
        "article",
        max_bullet_points=6,
        max_quotes=3,
        content="__PROMPT_PLACEHOLDER__",
    )

    splitter = "Content:"
    if splitter in template:
        return template.split(splitter)[0].strip()
    return template.strip()


def _truncate_text(value: str | None, limit: int) -> str | None:
    """Safely truncate text fields for LLM payloads."""

    if value is None:
        return None
    clean_value = value.strip()
    if len(clean_value) <= limit:
        return clean_value
    return clean_value[: limit - 3].rstrip() + "..."


def _clean_topics(raw_topics: Iterable[str] | None) -> list[str]:
    """Normalize topics collection."""

    if not raw_topics:
        return []
    topics: list[str] = []
    for topic in raw_topics:
        if isinstance(topic, str):
            stripped = topic.strip()
            if stripped:
                topics.append(stripped)
    return topics[:8]


def _extract_bullet_points(bullet_points: Iterable[dict[str, str]]) -> list[str]:
    """Extract bullet point text from structured summary payloads."""

    extracted: list[str] = []
    for bullet in bullet_points:
        if not isinstance(bullet, dict):
            continue
        text = bullet.get("text")
        if isinstance(text, str):
            trimmed = text.strip()
            if trimmed:
                extracted.append(_truncate_text(trimmed, 280) or "")
    return extracted[:8]
