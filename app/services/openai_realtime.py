"""OpenAI Realtime helpers."""

from __future__ import annotations

from typing import Any

import requests

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

REALTIME_CLIENT_SECRET_URL = "https://api.openai.com/v1/realtime/client_secrets"
REALTIME_TRANSCRIPTION_SESSION_URL = "https://api.openai.com/v1/realtime/transcription_sessions"
REALTIME_TOKEN_TTL_SECONDS = 600
REALTIME_DEFAULT_MODEL = "gpt-realtime"
REALTIME_TRANSCRIPTION_MODEL = "gpt-4o-mini-transcribe"
REALTIME_TRANSCRIPTION_SAMPLE_RATE = 24000


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


def build_transcription_session_config(*, locale: str | None = None) -> dict[str, Any]:
    """Build a transcription session configuration.

    Args:
        locale: Optional locale in ISO-639-1 format for transcription hints.

    Returns:
        Session config payload for a transcription session.
    """
    transcription_payload: dict[str, Any] = {
        "model": REALTIME_TRANSCRIPTION_MODEL,
    }
    if locale:
        transcription_payload["language"] = locale

    config: dict[str, Any] = {
        "input_audio_format": "pcm16",
        "input_audio_transcription": transcription_payload,
        "turn_detection": {"type": "server_vad"},
    }
    return config


def create_transcription_session_token(
    *, locale: str | None = None
) -> tuple[str, int | None, str | None]:
    """Create a short-lived OpenAI transcription session token.

    Args:
        locale: Optional locale in ISO-639-1 format for transcription hints.

    Returns:
        Tuple of (token, expires_at, model).
    """
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OpenAI API key is not configured")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = build_transcription_session_config(locale=locale)

    try:
        response = requests.post(
            REALTIME_TRANSCRIPTION_SESSION_URL,
            headers=headers,
            json=payload,
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.exception(
            "Realtime transcription session request failed",
            extra={
                "component": "openai_realtime",
                "operation": "transcription_session_request",
                "context_data": {"error": str(exc)},
            },
        )
        raise RuntimeError("Failed to contact OpenAI") from exc

    if response.status_code >= 400:
        logger.error(
            "Realtime transcription session request returned error",
            extra={
                "component": "openai_realtime",
                "operation": "transcription_session_request",
                "context_data": {
                    "status_code": response.status_code,
                    "body": response.text[:500],
                },
            },
        )
        raise RuntimeError("OpenAI transcription session request failed")

    payload = response.json()
    client_secret = payload.get("client_secret") or {}
    token = client_secret.get("value")
    expires_at = client_secret.get("expires_at")
    model = REALTIME_DEFAULT_MODEL

    if not token:
        raise RuntimeError("OpenAI transcription session response missing token")

    return token, expires_at, model
