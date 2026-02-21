"""Helpers for encrypting and decrypting integration tokens at rest."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.settings import get_settings


def _build_fernet() -> Fernet:
    """Return a Fernet instance derived from configured encryption key."""
    settings = get_settings()
    raw_key = (settings.x_token_encryption_key or "").strip()
    if not raw_key:
        raise ValueError("X_TOKEN_ENCRYPTION_KEY is required for integration token storage")

    key_bytes = raw_key.encode("utf-8")
    try:
        return Fernet(key_bytes)
    except ValueError:
        derived = base64.urlsafe_b64encode(hashlib.sha256(key_bytes).digest())
        return Fernet(derived)


def encrypt_token(raw_token: str) -> str:
    """Encrypt a token string for database storage."""
    if not raw_token:
        raise ValueError("Token must not be empty")
    return _build_fernet().encrypt(raw_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a previously encrypted token."""
    if not encrypted_token:
        raise ValueError("Encrypted token must not be empty")
    try:
        decrypted = _build_fernet().decrypt(encrypted_token.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted token payload") from exc
    return decrypted.decode("utf-8")
