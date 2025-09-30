"""
Generic Error Logger - Simple, universal error logging with full context capture.
"""

import json
import logging
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)
SCRAPER_METRICS: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


@dataclass
class ErrorContext:
    """Structured error context data."""

    timestamp: str
    component: str
    operation: str | None
    error_type: str
    error_message: str
    stack_trace: str | None = None
    context_data: dict[str, Any] | None = None
    http_details: dict[str, Any] | None = None
    item_id: str | int | None = None


class GenericErrorLogger:
    """
    Simple, universal error logger with full context capture.
    Designed to replace complex RSS-specific logger with better debugging info.
    """

    def __init__(self, component: str, log_dir: str | Path | None = None):
        self.component = component
        settings = get_settings()
        base_dir = Path(log_dir) if log_dir else settings.logs_dir / "errors"
        self.log_dir = base_dir.resolve()
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create timestamped log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{component}_{timestamp}.jsonl"

    def log_error(
        self,
        error: Exception,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
        http_response: Any | None = None,
        item_id: str | int | None = None,
    ) -> None:
        """Log error with full context."""

        # Extract HTTP details if response provided
        http_details = None
        if http_response:
            http_details = self._extract_http_details(http_response)

        error_context = ErrorContext(
            timestamp=datetime.now().isoformat(),
            component=self.component,
            operation=operation,
            error_type=type(error).__name__,
            error_message=str(error),
            stack_trace=traceback.format_exc(),
            context_data=context,
            http_details=http_details,
            item_id=item_id,
        )

        self._write_log(error_context)

        # Also log to console for immediate visibility
        operation_str = f" during {operation}" if operation else ""
        item_str = f" (item: {item_id})" if item_id else ""
        logger.error(f"{self.component} error{operation_str}{item_str}: {error}")

    def log_http_error(
        self,
        url: str,
        response: Any | None = None,
        error: Exception | None = None,
        operation: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Log HTTP-specific errors with response details."""

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
        """Log processing errors with item context."""

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
        """Log feed-specific errors (for RSS/feed processing)."""

        context = {
            "feed_url": feed_url,
            "feed_name": feed_name,
            "entries_processed": entries_processed,
        }

        self.log_error(error=error, operation=operation or "feed_processing", context=context)


def log_scraper_event(
    *,
    service: str,
    event: str,
    level: int = logging.INFO,
    metric: str | None = None,
    **fields: Any,
) -> None:
    """Emit a structured scraper event log and optionally increment metrics."""

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
    """Increment a scraper metric counter."""

    SCRAPER_METRICS[service][metric] += amount


def get_scraper_metrics() -> dict[str, dict[str, int]]:
    """Return current scraper metric counters (primarily for tests)."""

    return {service: dict(metrics) for service, metrics in SCRAPER_METRICS.items()}


def reset_scraper_metrics() -> None:
    """Clear scraper metrics. Useful in tests to avoid cross pollution."""

    SCRAPER_METRICS.clear()

    def _extract_http_details(self, response: Any) -> dict[str, Any]:
        """Extract useful details from HTTP response object."""
        details = {}

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

    def _write_log(self, error_context: ErrorContext) -> None:
        """Write error context to JSON Lines file."""
        try:
            with open(self.log_file, "a") as f:
                json_line = json.dumps(asdict(error_context), default=str, ensure_ascii=False)
                f.write(json_line + "\n")
        except Exception as e:
            logger.error(f"Failed to write error log: {e}")

    def get_recent_errors(self, limit: int = 10) -> list:
        """Get recent errors from log file."""
        errors = []
        try:
            if self.log_file.exists():
                with open(self.log_file) as f:
                    lines = f.readlines()
                    for line in lines[-limit:]:
                        try:
                            errors.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"Failed to read error log: {e}")

        return errors


def create_error_logger(component: str, log_dir: str | Path | None = None) -> GenericErrorLogger:
    """Factory function to create error logger.

    Args:
        component: Component name for scoping log files.
        log_dir: Optional override for the log directory.

    Returns:
        GenericErrorLogger: Configured error logger instance.
    """

    return GenericErrorLogger(component, log_dir)
