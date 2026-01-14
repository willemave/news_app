"""Shared LLM usage tracking for per-run aggregation."""

from __future__ import annotations

from contextvars import ContextVar, Token
from copy import deepcopy
from typing import Any

_USAGE_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "llm_usage_context", default=None
)


def start_usage_context() -> Token:
    """Start a new usage aggregation context."""
    return _USAGE_CONTEXT.set(
        {"total": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}, "steps": {}}
    )


def end_usage_context(token: Token) -> None:
    """End the current usage context."""
    _USAGE_CONTEXT.reset(token)


def snapshot_usage() -> dict[str, Any] | None:
    """Return a snapshot of the current usage aggregation."""
    usage = _USAGE_CONTEXT.get()
    if not usage:
        return None
    return deepcopy(usage)


def record_usage(step: str, result: object, *, model_spec: str | None = None) -> None:
    """Record usage for a single LLM call into the current context."""
    usage_context = _USAGE_CONTEXT.get()
    if usage_context is None:
        return

    usage = _extract_usage(result)
    if not usage:
        return

    step_entry = usage_context["steps"].setdefault(
        step,
        {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "calls": 0},
    )
    if model_spec:
        step_entry["model_spec"] = model_spec

    step_entry["calls"] += 1
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = usage.get(key)
        if value is None:
            continue
        step_entry[key] += value
        usage_context["total"][key] += value


def _extract_usage(result: object) -> dict[str, int | None] | None:
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


def _coerce_int(value: object | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
