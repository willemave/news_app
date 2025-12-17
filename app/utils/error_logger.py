"""
Generic Error Logger - Simple, universal error logging with full context capture.

This module provides structured error logging that integrates with the JSONL
error handler in app/core/logging.py. Errors are automatically written to
logs/errors/ in JSONL format via the standard logging infrastructure.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from app.core.logging import get_logger

SCRAPER_METRICS: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


class GenericErrorLogger:
    """
    Simple, universal error logger with full context capture.

    This logger uses Python's standard logging infrastructure with extra fields
    that are picked up by the JSONL error handler configured in setup_logging().
    Errors are automatically written to logs/errors/*.jsonl.
    """

    def __init__(self, component: str, log_dir: str | None = None):
        """
        Initialize the error logger.

        Args:
            component: Component name for identifying the source of errors.
            log_dir: Deprecated - no longer used. JSONL output is handled by
                     the centralized logging handler.
        """
        self.component = component
        self._logger = get_logger(f"error.{component}")
        if log_dir is not None:
            self._logger.debug(
                "log_dir parameter is deprecated; JSONL output is handled by setup_logging()"
            )

    def log_error(
        self,
        error: Exception,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
        http_response: Any | None = None,
        item_id: str | int | None = None,
    ) -> None:
        """Log error with full context.

        Args:
            error: The exception that occurred.
            operation: Name of the operation that failed.
            context: Additional context data.
            http_response: HTTP response object (if applicable).
            item_id: ID of the item being processed (if applicable).
        """
        # Extract HTTP details if response provided
        http_details = None
        if http_response:
            http_details = self._extract_http_details(http_response)

        # Build log message
        operation_str = f" during {operation}" if operation else ""
        item_str = f" (item: {item_id})" if item_id else ""
        message = f"{self.component} error{operation_str}{item_str}: {error}"

        # Use logger.exception to include stack trace, with extra fields for JSONL
        self._logger.exception(
            message,
            exc_info=error,
            extra={
                "component": self.component,
                "operation": operation,
                "context_data": context,
                "http_details": http_details,
                "item_id": item_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )

    def log_http_error(
        self,
        url: str,
        response: Any | None = None,
        error: Exception | None = None,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log HTTP-specific errors with response details.

        Args:
            url: The URL that was requested.
            response: HTTP response object (if available).
            error: The exception that occurred (if any).
            operation: Name of the operation that failed.
            context: Additional context data.
        """
        # Build context with URL
        full_context = {"url": url}
        if context:
            full_context.update(context)

        # Use provided error or create a generic one
        if not error:
            status_code = getattr(response, "status_code", "unknown")
            error = Exception(f"HTTP error for {url} (status: {status_code})")

        self.log_error(
            error=error,
            operation=operation or "http_request",
            context=full_context,
            http_response=response,
        )

    def log_processing_error(
        self,
        item_id: str | int,
        error: Exception,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log processing errors with item context.

        Args:
            item_id: ID of the item being processed.
            error: The exception that occurred.
            operation: Name of the operation that failed.
            context: Additional context data.
        """
        self.log_error(
            error=error,
            operation=operation or "content_processing",
            context=context,
            item_id=item_id,
        )

    def log_feed_error(
        self,
        feed_url: str,
        error: Exception,
        feed_name: str | None = None,
        entries_processed: int | None = None,
        operation: str | None = None,
    ) -> None:
        """Log feed-specific errors (for RSS/feed processing).

        Args:
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

        self.log_error(error=error, operation=operation or "feed_processing", context=context)

    def _extract_http_details(self, response: Any) -> dict[str, Any]:
        """Extract useful details from HTTP response object.

        Args:
            response: HTTP response object.

        Returns:
            Dictionary with extracted HTTP details.
        """
        details: dict[str, Any] = {}

        try:
            # Handle different response object types
            if hasattr(response, "status_code"):
                details["status_code"] = response.status_code
            if hasattr(response, "headers"):
                # Convert headers to dict, limit size
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

            # Get response content (limited size)
            if hasattr(response, "text"):
                content = response.text[:1000]  # Limit to first 1KB
                details["response_body"] = content
            elif hasattr(response, "content"):
                content = str(response.content)[:1000]
                details["response_body"] = content

        except Exception as e:
            details["extraction_error"] = f"Failed to extract HTTP details: {e}"

        return details

    def get_recent_errors(self, limit: int = 10) -> list:
        """Get recent errors - deprecated, use logs router instead.

        This method is deprecated. Recent errors can be retrieved via the
        admin logs API which reads from the centralized JSONL files.

        Args:
            limit: Maximum number of errors to return.

        Returns:
            Empty list (deprecated functionality).
        """
        self._logger.warning("get_recent_errors() is deprecated; use the admin logs API instead")
        return []


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


def create_error_logger(component: str, log_dir: str | None = None) -> GenericErrorLogger:
    """Factory function to create error logger.

    Args:
        component: Component name for scoping log files.
        log_dir: Deprecated - no longer used.

    Returns:
        GenericErrorLogger: Configured error logger instance.
    """
    return GenericErrorLogger(component, log_dir)
