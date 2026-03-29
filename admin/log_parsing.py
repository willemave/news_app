"""Log parsing helpers shared by local and remote admin flows."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

_SERVICE_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - "
    r"(?P<logger>.+?) - "
    r"(?P<level>[A-Z]+) - "
    r"\[(?P<source>[^\]]+)\] - "
    r"(?P<message>.*)$"
)


def parse_jsonl_record(raw_line: str, *, source: str, file_path: str) -> dict[str, Any] | None:
    """Parse one structured JSONL record."""
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None
    payload["source"] = source
    payload["file_path"] = file_path
    return payload


def parse_service_log_line(raw_line: str, *, source: str, file_path: str) -> dict[str, Any] | None:
    """Parse one service log line into a searchable record."""
    match = _SERVICE_LOG_PATTERN.match(raw_line.strip())
    if match is None:
        return None

    parsed: dict[str, Any] = {
        "timestamp": match.group("timestamp"),
        "logger": match.group("logger"),
        "level": match.group("level"),
        "message": match.group("message"),
        "source": source,
        "file_path": file_path,
    }
    message = parsed["message"]
    if " | " in message:
        message_body, suffix = message.split(" | ", 1)
        parsed["message"] = message_body
        parsed.update(_parse_suffix_fields(suffix))
    return parsed


def parse_record_timestamp(record: dict[str, Any]) -> datetime | None:
    """Parse supported timestamp formats from a log record."""
    raw_value = record.get("timestamp")
    if not raw_value:
        return None
    if isinstance(raw_value, datetime):
        return raw_value
    text = str(raw_value).strip()
    if not text:
        return None
    try:
        if "T" in text:
            normalized = text.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def record_matches_query(record: dict[str, Any], query: str | None) -> bool:
    """Return whether the record matches a free-text query."""
    if not query:
        return True
    haystack = json.dumps(record, ensure_ascii=False, default=str).lower()
    return query.lower() in haystack


def record_matches_filters(record: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Return whether top-level structured fields match exact filters."""
    for key, expected in filters.items():
        if expected in (None, ""):
            continue
        actual = record.get(key)
        if actual is None and isinstance(record.get("context_data"), dict):
            actual = record["context_data"].get(key)
        if str(actual) != str(expected):
            return False
    return True


def _parse_suffix_fields(raw_suffix: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for token in raw_suffix.split(" "):
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        parsed[key] = value
    return parsed
