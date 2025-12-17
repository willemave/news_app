"""
Structured Error Logging - Simple functions for error logging with full context.

This module provides structured error logging that integrates with the JSONL
error handler in app/core/logging.py. Errors are automatically written to
logs/errors/ in JSONL format via the standard logging infrastructure.

Usage:
    from app.utils.error_logger import log_error, log_processing_error, log_http_error

    # Basic error logging
    log_error("component_name", error, operation="task_name", context={"key": "value"})

    # Processing errors (with item_id)
    log_processing_error("worker", item_id=123, error=e, operation="summarize")

    # HTTP errors
    log_http_error("http_client", url="https://...", error=e, response=resp)
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.core.logging import get_logger

SCRAPER_METRICS: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def _extract_http_details(response: Any) -> dict[str, Any]:
    """Extract useful details from HTTP response object.

    Args:
        response: HTTP response object.

    Returns:
        Dictionary with extracted HTTP details.
    """
    details: dict[str, Any] = {}

    try:
        if hasattr(response, "status_code"):
            details["status_code"] = response.status_code
        if hasattr(response, "headers"):
            headers = dict(response.headers)
            details["headers"] = {
                k: v[:200] if isinstance(v, str) else v for k, v in headers.items()
            }
        if hasattr(response, "url"):
            details["url"] = str(response.url)
        if hasattr(response, "request"):
            if hasattr(response.request, "method"):
                details["method"] = response.request.method
            if hasattr(response.request, "url"):
                details["request_url"] = str(response.request.url)

        if hasattr(response, "text"):
            details["response_body"] = response.text[:1000]
        elif hasattr(response, "content"):
            details["response_body"] = str(response.content)[:1000]

    except Exception as e:
        details["extraction_error"] = f"Failed to extract HTTP details: {e}"

    return details


def log_error(
    component: str,
    error: Exception,
    *,
    operation: str | None = None,
    context: dict[str, Any] | None = None,
    http_response: Any | None = None,
    item_id: str | int | None = None,
) -> None:
    """Log error with full context to both console and JSONL.

    Args:
        component: Component name for identifying the source of errors.
        error: The exception that occurred.
        operation: Name of the operation that failed.
        context: Additional context data.
        http_response: HTTP response object (if applicable).
        item_id: ID of the item being processed (if applicable).
    """
    logger = get_logger(f"error.{component}")

    http_details = None
    if http_response:
        http_details = _extract_http_details(http_response)

    operation_str = f" during {operation}" if operation else ""
    item_str = f" (item: {item_id})" if item_id else ""
    message = f"{component} error{operation_str}{item_str}: {error}"

    logger.exception(
        message,
        exc_info=error,
        extra={
            "component": component,
            "operation": operation,
            "context_data": context,
            "http_details": http_details,
            "item_id": item_id,
            "error_type": type(error).__name__,
            "error_message": str(error),
        },
    )


def log_processing_error(
    component: str,
    item_id: str | int,
    error: Exception,
    *,
    operation: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Log processing errors with item context.

    Args:
        component: Component name for identifying the source of errors.
        item_id: ID of the item being processed.
        error: The exception that occurred.
        operation: Name of the operation that failed.
        context: Additional context data.
    """
    log_error(
        component,
        error,
        operation=operation or "content_processing",
        context=context,
        item_id=item_id,
    )


def log_http_error(
    component: str,
    url: str,
    *,
    response: Any | None = None,
    error: Exception | None = None,
    operation: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    """Log HTTP-specific errors with response details.

    Args:
        component: Component name for identifying the source of errors.
        url: The URL that was requested.
        response: HTTP response object (if available).
        error: The exception that occurred (if any).
        operation: Name of the operation that failed.
        context: Additional context data.
    """
    full_context = {"url": url}
    if context:
        full_context.update(context)

    if not error:
        status_code = getattr(response, "status_code", "unknown")
        error = Exception(f"HTTP error for {url} (status: {status_code})")

    log_error(
        component,
        error,
        operation=operation or "http_request",
        context=full_context,
        http_response=response,
    )


def log_feed_error(
    component: str,
    feed_url: str,
    error: Exception,
    *,
    feed_name: str | None = None,
    entries_processed: int | None = None,
    operation: str | None = None,
) -> None:
    """Log feed-specific errors (for RSS/feed processing).

    Args:
        component: Component name for identifying the source of errors.
        feed_url: URL of the feed that failed.
        error: The exception that occurred.
        feed_name: Name of the feed (if known).
        entries_processed: Number of entries processed before failure.
        operation: Name of the operation that failed.
    """
    context = {
        "feed_url": feed_url,
        "feed_name": feed_name,
        "entries_processed": entries_processed,
    }

    log_error(
        component,
        error,
        operation=operation or "feed_processing",
        context=context,
    )


# Scraper event logging (unchanged)


def log_scraper_event(
    *,
    service: str,
    event: str,
    level: int = logging.INFO,
    metric: str | None = None,
    **fields: Any,
) -> None:
    """Emit a structured scraper event log and optionally increment metrics.

    Args:
        service: Name of the scraper service.
        event: Event type/name.
        level: Log level (default INFO).
        metric: Metric name to increment (optional).
        **fields: Additional fields to include in the log.
    """
    logger = get_logger(f"scraper.{service}")

    payload = {
        "timestamp": datetime.now().isoformat(),
        "service": service,
        "event": event,
    }
    payload.update({k: v for k, v in fields.items() if v is not None})

    logger.log(level, "SCRAPER_EVENT %s", json.dumps(payload, ensure_ascii=False))

    if metric:
        SCRAPER_METRICS[service][metric] += 1


def increment_scraper_metric(service: str, metric: str, amount: int = 1) -> None:
    """Increment a scraper metric counter.

    Args:
        service: Name of the scraper service.
        metric: Metric name to increment.
        amount: Amount to increment by (default 1).
    """
    SCRAPER_METRICS[service][metric] += amount


def get_scraper_metrics() -> dict[str, dict[str, int]]:
    """Return current scraper metric counters (primarily for tests).

    Returns:
        Dictionary mapping service names to metric dictionaries.
    """
    return {service: dict(metrics) for service, metrics in SCRAPER_METRICS.items()}


def reset_scraper_metrics() -> None:
    """Clear scraper metrics. Useful in tests to avoid cross pollution."""
    SCRAPER_METRICS.clear()
