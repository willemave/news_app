"""Helpers for generating, parsing, hashing, and verifying user API keys."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass

API_KEY_TOKEN_PREFIX = "newsly_ak_"


@dataclass(frozen=True)
class GeneratedApiKey:
    """One newly generated API key."""

    raw_key: str
    key_prefix: str


def is_api_key_token(token: str) -> bool:
    """Return whether a bearer token looks like a Newsly API key."""
    return token.startswith(API_KEY_TOKEN_PREFIX)


def extract_key_prefix(raw_key: str) -> str:
    """Return the lookup prefix for a raw API key."""
    if not is_api_key_token(raw_key):
        raise ValueError("Invalid API key format")
    suffix = raw_key.removeprefix(API_KEY_TOKEN_PREFIX)
    public_id, separator, _secret = suffix.partition("_")
    if not public_id or not separator:
        raise ValueError("Invalid API key format")
    return f"{API_KEY_TOKEN_PREFIX}{public_id}"


def generate_api_key() -> GeneratedApiKey:
    """Create a new API key with a stable lookup prefix."""
    public_id = secrets.token_hex(4)
    secret = secrets.token_urlsafe(24)
    key_prefix = f"{API_KEY_TOKEN_PREFIX}{public_id}"
    return GeneratedApiKey(
        raw_key=f"{key_prefix}_{secret}",
        key_prefix=key_prefix,
    )


def hash_api_key(raw_key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def verify_api_key_hash(raw_key: str, key_hash: str) -> bool:
    """Verify an API key against a stored hash."""
    calculated = hash_api_key(raw_key)
    return hmac.compare_digest(calculated, key_hash)
