"""Helpers for logging deprecated field usage."""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_LOGGED_DEPRECATED_FIELDS: set[tuple[str, str | None, str, str, int | None]] = set()


def clear_deprecated_field_cache() -> None:
    """Clear the in-memory cache of deprecated field logs."""
    _LOGGED_DEPRECATED_FIELDS.clear()


def log_deprecated_field(
    *,
    field_name: str,
    component: str,
    operation: str,
    item_id: int | None = None,
    replacement: str | None = None,
    context_data: dict[str, Any] | None = None,
    once: bool = True,
) -> None:
    """Log usage of a deprecated field with structured metadata.

    Args:
        field_name: Deprecated field name (e.g., "summary.overview").
        component: Module or worker name emitting the log.
        operation: Operation being performed when field was seen.
        item_id: Optional content/item identifier.
        replacement: Suggested replacement field name.
        context_data: Optional additional context to include in log record.
        once: If True, log only once per field/component/operation/item_id tuple.
    """
    cache_key = (field_name, replacement, component, operation, item_id)
    if once:
        if cache_key in _LOGGED_DEPRECATED_FIELDS:
            return
        _LOGGED_DEPRECATED_FIELDS.add(cache_key)

    payload = {"deprecated_field": field_name}
    if replacement:
        payload["replacement"] = replacement
    if context_data:
        payload.update(context_data)

    logger.warning(
        "Deprecated field encountered: %s",
        field_name,
        extra={
            "component": component,
            "operation": operation,
            "item_id": item_id,
            "context_data": payload,
        },
    )
