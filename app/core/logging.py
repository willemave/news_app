import json
import logging
import os
import re
import sys
import traceback
from datetime import UTC, datetime
from functools import lru_cache
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any

from app.core.settings import get_settings

_STANDARD_LOG_RECORD_KEYS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())
_STANDARD_LOG_RECORD_KEYS.update({"message", "asctime"})
_STRUCTURED_LOG_KEYS = {
    "component",
    "operation",
    "item_id",
    "context_data",
    "http_details",
    "error_type",
    "error_message",
}


def _sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip().lower())
    return cleaned.strip("._-") or "app"


def _redact_value(value: Any) -> Any:
    sensitive_keys = {
        "authorization",
        "cookie",
        "set-cookie",
        "x-api-key",
        "api-key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "password",
        "secret",
        "jwt",
        "jwt_secret_key",
    }

    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if any(part in key.lower() for part in sensitive_keys):
                out[key] = "<redacted>"
            else:
                out[key] = _redact_value(v)
        return out

    if isinstance(value, list):
        return [_redact_value(v) for v in value]

    if isinstance(value, tuple):
        return tuple(_redact_value(v) for v in value)

    if isinstance(value, str):
        redacted = re.sub(
            r"(?i)\bbearer\s+[a-z0-9\-._~+/]+=*",
            "Bearer <redacted>",
            value,
        )
        redacted = re.sub(
            r"(?i)(authorization['\"]?\s*[:=]\s*['\"])([^'\"]+)(['\"])",
            r"\1<redacted>\3",
            redacted,
        )
        redacted = re.sub(
            r"(?i)(cookie['\"]?\s*[:=]\s*['\"])([^'\"]+)(['\"])",
            r"\1<redacted>\3",
            redacted,
        )
        return redacted

    return value


def _default_log_record_component(record: logging.LogRecord) -> str:
    component = getattr(record, "component", None)
    if isinstance(component, str) and component.strip():
        return component
    return record.name


def _extract_extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    extra_fields: dict[str, Any] = {}
    for key, value in record.__dict__.items():
        if key in _STANDARD_LOG_RECORD_KEYS or key in _STRUCTURED_LOG_KEYS:
            continue
        extra_fields[key] = value
    return extra_fields


def _merge_context_data(context_data: Any, extra_fields: dict[str, Any]) -> Any:
    if not extra_fields:
        return context_data
    if context_data is None:
        return extra_fields
    if isinstance(context_data, dict):
        merged = dict(extra_fields)
        merged.update(context_data)
        return merged
    return {"context_data": context_data, **extra_fields}


def _build_error_json_payload(record: logging.LogRecord) -> dict[str, Any]:
    message = _redact_value(record.getMessage())

    exc_type = None
    exc_value = None
    exc_tb = None
    if record.exc_info and len(record.exc_info) == 3:
        exc_type, exc_value, exc_tb = record.exc_info

    error_type = getattr(record, "error_type", None)
    if not error_type and exc_type:
        error_type = exc_type.__name__
    if not error_type:
        error_type = "LogError"

    error_message = getattr(record, "error_message", None)
    if not error_message and exc_value:
        error_message = str(exc_value)
    if not error_message:
        error_message = str(message)

    stack_trace = None
    if exc_type and exc_value and exc_tb:
        stack_trace = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))

    context_data = _merge_context_data(
        getattr(record, "context_data", None), _extract_extra_fields(record)
    )
    if context_data is not None:
        context_data = _redact_value(context_data)

    http_details = getattr(record, "http_details", None)
    if http_details is not None:
        http_details = _redact_value(http_details)

    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "component": _default_log_record_component(record),
        "operation": getattr(record, "operation", None),
        "error_type": error_type,
        "error_message": error_message,
        "stack_trace": stack_trace,
        "message": message,
        "context_data": context_data,
        "http_details": http_details,
        "item_id": getattr(record, "item_id", None),
        "source_file": record.filename,
        "source_line": record.lineno,
        "source_function": record.funcName,
        "process": record.process,
        "thread": record.thread,
    }

    return {k: v for k, v in payload.items() if v is not None}


class _JsonLineErrorFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = _build_error_json_payload(record)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _build_structured_json_payload(record: logging.LogRecord) -> dict[str, Any]:
    message = _redact_value(record.getMessage())

    context_data = _merge_context_data(
        getattr(record, "context_data", None), _extract_extra_fields(record)
    )
    if context_data is not None:
        context_data = _redact_value(context_data)

    http_details = getattr(record, "http_details", None)
    if http_details is not None:
        http_details = _redact_value(http_details)

    payload: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": record.levelname,
        "logger": record.name,
        "component": _default_log_record_component(record),
        "operation": getattr(record, "operation", None),
        "message": message,
        "context_data": context_data,
        "http_details": http_details,
        "item_id": getattr(record, "item_id", None),
        "source_file": record.filename,
        "source_line": record.lineno,
        "source_function": record.funcName,
        "process": record.process,
        "thread": record.thread,
    }

    return {k: v for k, v in payload.items() if v is not None}


class _JsonLineStructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = _build_structured_json_payload(record)
        return json.dumps(payload, ensure_ascii=False, default=str)


class _StructuredLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "context_data", None) is not None:
            return True
        if getattr(record, "http_details", None) is not None:
            return True
        if getattr(record, "item_id", None) is not None:
            return True
        if getattr(record, "operation", None) is not None:
            return True
        return bool(_extract_extra_fields(record))


def _rotate_jsonl_namer(default_name: str) -> str:
    marker = ".jsonl."
    if marker not in default_name:
        return default_name
    before, after = default_name.split(marker, 1)
    return f"{before}_{after}.jsonl"


def _create_error_jsonl_handler(*, errors_dir: Path, logger_name: str) -> logging.Handler:
    errors_dir.mkdir(parents=True, exist_ok=True)
    prefix = _sanitize_filename(logger_name)
    base_file = errors_dir / f"{prefix}_errors_{os.getpid()}.jsonl"

    handler = TimedRotatingFileHandler(
        filename=str(base_file),
        when="D",
        interval=1,
        backupCount=0,
        encoding="utf-8",
        delay=True,
        utc=True,
    )
    handler.setLevel(logging.ERROR)
    handler.setFormatter(_JsonLineErrorFormatter())
    handler.suffix = "%Y%m%d_%H%M%S"
    handler.namer = _rotate_jsonl_namer
    return handler


def _create_structured_jsonl_handler(*, structured_dir: Path, logger_name: str) -> logging.Handler:
    structured_dir.mkdir(parents=True, exist_ok=True)
    prefix = _sanitize_filename(logger_name)
    base_file = structured_dir / f"{prefix}_structured_{os.getpid()}.jsonl"

    handler = TimedRotatingFileHandler(
        filename=str(base_file),
        when="D",
        interval=1,
        backupCount=0,
        encoding="utf-8",
        delay=True,
        utc=True,
    )
    handler.setLevel(logging.NOTSET)
    handler.setFormatter(_JsonLineStructuredFormatter())
    handler.addFilter(_StructuredLogFilter())
    handler.suffix = "%Y%m%d_%H%M%S"
    handler.namer = _rotate_jsonl_namer
    return handler


@lru_cache
def setup_logging(name: str | None = None, level: str | None = None) -> logging.Logger:
    """
    Set up logging configuration for the entire application.

    Args:
        name: Logger name (defaults to app name from settings)
        level: Log level (defaults to settings.log_level)

    Returns:
        Configured logger instance
    """
    settings = get_settings()
    logger_name = name or settings.app_name
    log_level = level or settings.log_level

    # Configure the root logger instead of a specific named logger
    # This ensures all child loggers inherit the configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers from root logger
    root_logger.handlers.clear()

    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    # Format with more context
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)

    error_handler = _create_error_jsonl_handler(
        errors_dir=settings.logs_dir / "errors",
        logger_name=logger_name,
    )
    root_logger.addHandler(error_handler)

    structured_handler = _create_structured_jsonl_handler(
        structured_dir=settings.logs_dir / "structured",
        logger_name=logger_name,
    )
    root_logger.addHandler(structured_handler)

    # Also return the app-specific logger for backward compatibility
    app_logger = logging.getLogger(logger_name)
    app_logger.setLevel(getattr(logging, log_level.upper()))

    return app_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
