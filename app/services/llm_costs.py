"""Shared persistence and pricing helpers for LLM usage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.observability import build_log_extra
from app.models.schema import LlmUsageRecord
from app.services.llm_models import resolve_model_provider

logger = get_logger("llm.cost")

PRICING_VERSION = "2026-03-28"
USD = "USD"


@dataclass(frozen=True)
class ModelPricing:
    input_per_million_usd: float | None
    output_per_million_usd: float | None
    long_context_threshold_tokens: int | None = None
    long_context_input_per_million_usd: float | None = None
    long_context_output_per_million_usd: float | None = None


# Standard online pricing for the exact model names we resolve in production.
# For preview snapshots vendors no longer list directly, we pin the nearest current
# official pricing for the same model family and keep the alias explicit below.
MODEL_PRICING: dict[str, ModelPricing] = {
    # OpenAI
    "gpt-5.4": ModelPricing(
        input_per_million_usd=2.50,
        output_per_million_usd=15.00,
        long_context_threshold_tokens=272_000,
        long_context_input_per_million_usd=5.00,
        long_context_output_per_million_usd=22.50,
    ),
    "gpt-5.4-mini": ModelPricing(
        input_per_million_usd=0.75,
        output_per_million_usd=4.50,
    ),
    "gpt-4o": ModelPricing(
        input_per_million_usd=2.50,
        output_per_million_usd=10.00,
    ),
    "o4-mini-deep-research": ModelPricing(
        input_per_million_usd=2.00,
        output_per_million_usd=8.00,
    ),
    # Anthropic
    "claude-opus-4-5-20251101": ModelPricing(
        input_per_million_usd=5.00,
        output_per_million_usd=25.00,
    ),
    "claude-sonnet-4-5-20250929": ModelPricing(
        input_per_million_usd=3.00,
        output_per_million_usd=15.00,
    ),
    # Google
    "gemini-3.1-pro-preview": ModelPricing(
        input_per_million_usd=2.00,
        output_per_million_usd=12.00,
        long_context_threshold_tokens=200_000,
        long_context_input_per_million_usd=4.00,
        long_context_output_per_million_usd=18.00,
    ),
    "gemini-3.1-flash-lite-preview": ModelPricing(
        input_per_million_usd=0.25,
        output_per_million_usd=1.50,
    ),
    "gemini-3-flash-preview": ModelPricing(
        input_per_million_usd=0.50,
        output_per_million_usd=3.00,
    ),
    # Image generation output for Gemini image-preview models is token-priced by Google.
    "gemini-3.1-flash-image-preview": ModelPricing(
        input_per_million_usd=0.50,
        output_per_million_usd=60.00,
    ),
}


# Older snapshots and repo-specific aliases that should inherit canonical pricing.
MODEL_ALIASES: dict[str, str] = {
    "claude-opus-4-5": "claude-opus-4-5-20251101",
    "claude-sonnet-4-5": "claude-sonnet-4-5-20250929",
    "gemini-3-pro-preview": "gemini-3.1-pro-preview",
    "o4-mini-deep-research-2025-06-26": "o4-mini-deep-research",
}


def extract_usage_from_result(result: object) -> dict[str, int | None] | None:
    """Extract token usage from a pydantic-ai style result object."""
    try:
        usage = result.usage()
    except Exception:  # noqa: BLE001
        return None

    if not usage:
        return None

    input_tokens = _coerce_int(
        getattr(usage, "input_tokens", None) or getattr(usage, "prompt_tokens", None)
    )
    output_tokens = _coerce_int(
        getattr(usage, "output_tokens", None) or getattr(usage, "completion_tokens", None)
    )
    total_tokens = _coerce_int(getattr(usage, "total_tokens", None))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens

    if input_tokens is None and output_tokens is None and total_tokens is None:
        return None

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def record_llm_usage(
    db: Session,
    *,
    provider: str | None,
    model: str,
    feature: str,
    operation: str,
    source: str | None = None,
    usage: dict[str, int | None] | None,
    request_id: str | None = None,
    task_id: int | None = None,
    content_id: int | None = None,
    session_id: int | None = None,
    message_id: int | None = None,
    user_id: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> LlmUsageRecord | None:
    """Persist one LLM usage record and emit a structured log."""
    if usage is None:
        return None

    provider_name = provider or resolve_model_provider(model)
    input_tokens = usage.get("input_tokens", usage.get("input"))
    output_tokens = usage.get("output_tokens", usage.get("output"))
    total_tokens = usage.get("total_tokens", usage.get("total"))
    cost_usd = estimate_cost_usd(
        provider=provider_name,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )
    record = LlmUsageRecord(
        provider=provider_name,
        model=model,
        feature=feature,
        operation=operation,
        source=source,
        request_id=request_id,
        task_id=task_id,
        content_id=content_id,
        session_id=session_id,
        message_id=message_id,
        user_id=user_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        currency=USD,
        pricing_version=PRICING_VERSION,
        metadata_json=metadata or {},
    )
    db.add(record)
    db.flush()

    logger.info(
        "Recorded LLM usage",
        extra=build_log_extra(
            component="llm_costs",
            operation=operation,
            event_name="llm.usage",
            status="completed",
            request_id=request_id,
            task_id=task_id,
            content_id=content_id,
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            source=source,
            context_data={
                "provider": provider_name,
                "model": model,
                "feature": feature,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": cost_usd,
                "pricing_version": PRICING_VERSION,
            },
        ),
    )

    return record


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> float | None:
    """Estimate USD cost from the configured local pricing registry."""
    pricing = _resolve_pricing(provider=provider, model=model)
    if pricing is None:
        return None
    if input_tokens is None or output_tokens is None:
        return None

    input_rate = pricing.input_per_million_usd
    output_rate = pricing.output_per_million_usd
    if (
        pricing.long_context_threshold_tokens is not None
        and input_tokens > pricing.long_context_threshold_tokens
    ):
        input_rate = pricing.long_context_input_per_million_usd or input_rate
        output_rate = pricing.long_context_output_per_million_usd or output_rate

    if input_rate is None or output_rate is None:
        return None

    cost = (
        (input_tokens / 1_000_000) * input_rate + (output_tokens / 1_000_000) * output_rate
    )
    return round(cost, 8)


def _resolve_pricing(*, provider: str, model: str) -> ModelPricing | None:
    for candidate in _pricing_candidates(provider=provider, model=model):
        if candidate in MODEL_PRICING:
            return MODEL_PRICING[candidate]
    return MODEL_PRICING.get(provider)


def _pricing_candidates(*, provider: str, model: str) -> list[str]:
    candidates: list[str] = []

    def _add(value: str | None) -> None:
        if value and value not in candidates:
            candidates.append(value)

    _add(model)
    model_name = model.split(":", 1)[1] if ":" in model else model
    _add(model_name)

    for candidate in list(candidates):
        _add(MODEL_ALIASES.get(candidate))

    _add(f"{provider}:{model}")
    if model_name:
        _add(f"{provider}:{model_name}")
        aliased_name = MODEL_ALIASES.get(model_name)
        if aliased_name:
            _add(aliased_name)
            _add(f"{provider}:{aliased_name}")

    return candidates


def _coerce_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
