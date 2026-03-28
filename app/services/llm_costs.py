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


# Update this map as vendors change pricing. Unknown models persist usage with null cost.
MODEL_PRICING: dict[str, ModelPricing] = {}


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
    if pricing.input_per_million_usd is None or pricing.output_per_million_usd is None:
        return None
    if input_tokens is None or output_tokens is None:
        return None
    cost = (
        (input_tokens / 1_000_000) * pricing.input_per_million_usd
        + (output_tokens / 1_000_000) * pricing.output_per_million_usd
    )
    return round(cost, 8)


def _resolve_pricing(*, provider: str, model: str) -> ModelPricing | None:
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    prefixed = f"{provider}:{model}"
    if prefixed in MODEL_PRICING:
        return MODEL_PRICING[prefixed]
    return MODEL_PRICING.get(provider)


def _coerce_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
