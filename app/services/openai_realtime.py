"""OpenAI Realtime helpers."""

from __future__ import annotations

from typing import Any

import requests

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

REALTIME_CLIENT_SECRET_URL = "https://api.openai.com/v1/realtime/client_secrets"
REALTIME_TOKEN_TTL_SECONDS = 600


def create_realtime_client_secret(
    *, session: dict[str, Any] | None = None
) -> tuple[str, int | None, str | None]:
    """Create a short-lived OpenAI Realtime client secret.

    Args:
        session: Optional session configuration to bind to the token.

    Returns:
        Tuple of (token, expires_at, model).
    """
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OpenAI API key is not configured")

    payload: dict[str, Any] = {
        "expires_after": {"anchor": "created_at", "seconds": REALTIME_TOKEN_TTL_SECONDS},
    }
    if session:
        payload["session"] = session

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            REALTIME_CLIENT_SECRET_URL,
            headers=headers,
            json=payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.exception(
            "Realtime client secret request failed",
            extra={
                "component": "openai_realtime",
                "operation": "client_secret_request",
                "context_data": {"error": str(exc)},
            },
        )
        raise RuntimeError("Failed to contact OpenAI") from exc

    if response.status_code >= 400:
        logger.error(
            "Realtime client secret request returned error",
            extra={
                "component": "openai_realtime",
                "operation": "client_secret_request",
                "context_data": {
                    "status_code": response.status_code,
                    "body": response.text[:500],
                },
            },
        )
        raise RuntimeError("OpenAI client secret request failed")

    payload = response.json()
    if "value" in payload:
        token = payload.get("value")
        expires_at = payload.get("expires_at")
        session_payload = payload.get("session")
        model = None
        if isinstance(session_payload, dict):
            model = session_payload.get("model")
    elif isinstance(payload.get("client_secret"), dict):
        client_secret = payload.get("client_secret") or {}
        token = client_secret.get("value")
        expires_at = client_secret.get("expires_at")
        session_payload = payload.get("session")
        model = None
        if isinstance(session_payload, dict):
            model = session_payload.get("model")
    else:
        raise RuntimeError("OpenAI client secret response missing token")

    if not token:
        raise RuntimeError("OpenAI client secret response missing token")

    return token, expires_at, model
