"""Shared sensitive-data redaction helpers."""

from __future__ import annotations

import re
from typing import Any

REDACTED_VALUE = "<redacted>"
SENSITIVE_KEY_PARTS = {
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
    "passcode",
    "secret",
    "jwt",
    "jwt_secret_key",
    "id_token",
}


def redact_value(value: Any) -> Any:
    """Recursively redact known sensitive fields from nested values."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested_value in value.items():
            normalized_key = str(key)
            if any(part in normalized_key.lower() for part in SENSITIVE_KEY_PARTS):
                redacted[normalized_key] = REDACTED_VALUE
            else:
                redacted[normalized_key] = redact_value(nested_value)
        return redacted

    if isinstance(value, list):
        return [redact_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)

    if isinstance(value, str):
        bearer_redacted = re.sub(
            r"(?i)\bbearer\s+[a-z0-9\-._~+/]+=*",
            "Bearer <redacted>",
            value,
        )
        authorization_redacted = re.sub(
            r"(?i)(authorization['\"]?\s*[:=]\s*['\"])([^'\"]+)(['\"])",
            r"\1<redacted>\3",
            bearer_redacted,
        )
        return re.sub(
            r"(?i)(cookie['\"]?\s*[:=]\s*['\"])([^'\"]+)(['\"])",
            r"\1<redacted>\3",
            authorization_redacted,
        )

    return value
