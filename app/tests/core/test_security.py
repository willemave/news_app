"""Tests for security utilities."""
from datetime import timedelta

import jwt
import pytest

from app.core.security import create_access_token, create_refresh_token, verify_token
from app.core.settings import get_settings


def test_create_access_token():
    """Test access token creation."""
    user_id = 123
    token = create_access_token(user_id)

    assert isinstance(token, str)
    assert len(token) > 0

    # Decode and verify
    settings = get_settings()
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"
    assert "exp" in payload


def test_create_refresh_token():
    """Test refresh token creation."""
    user_id = 456
    token = create_refresh_token(user_id)

    assert isinstance(token, str)
    assert len(token) > 0

    # Decode and verify
    settings = get_settings()
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"


def test_verify_token_valid():
    """Test token verification with valid token."""
    user_id = 789
    token = create_access_token(user_id)

    payload = verify_token(token)

    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_verify_token_expired():
    """Test token verification with expired token."""
    from app.core.security import create_token

    # Create token that expired 1 hour ago
    user_id = 999
    token = create_token(user_id, "access", timedelta(hours=-1))

    with pytest.raises(jwt.ExpiredSignatureError):
        verify_token(token)


def test_verify_token_invalid():
    """Test token verification with invalid token."""
    with pytest.raises(jwt.InvalidTokenError):
        verify_token("invalid.token.here")
