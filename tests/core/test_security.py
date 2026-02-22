"""Tests for security utilities."""
from datetime import timedelta, datetime, UTC

import jwt
import pytest

from app.core.security import create_access_token, create_refresh_token, verify_token, verify_apple_token
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


def test_verify_apple_token_mvp_decode():
    """
    Test that verify_apple_token can decode Apple JWT tokens without verification (MVP).

    This creates a mock Apple-like JWT token and verifies that the function can decode it.
    In MVP mode, we skip signature verification as documented in the security warnings.
    """
    # Create a mock Apple JWT token (simulating what Apple would send)
    # In reality, Apple signs with RS256, but for MVP we're skipping verification
    mock_apple_claims = {
        "iss": "https://appleid.apple.com",
        "aud": "com.example.newsly",  # Your app's bundle ID
        "sub": "001234.abcdef123456.7890",  # Apple user ID
        "email": "test@icloud.com",
        "email_verified": True,
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
    }

    # Create a JWT token (we'll use a dummy key since MVP doesn't verify)
    # In production, Apple would sign this with their private key
    test_token = jwt.encode(mock_apple_claims, "dummy-key", algorithm="HS256")

    # This should decode successfully for MVP (without signature verification)
    claims = verify_apple_token(test_token)

    # Verify the claims were extracted correctly
    assert claims["sub"] == "001234.abcdef123456.7890"
    assert claims["email"] == "test@icloud.com"
    assert claims["iss"] == "https://appleid.apple.com"


def test_verify_apple_token_missing_required_claims():
    """Test that verify_apple_token validates required claims."""
    # Create token missing issuer claim
    invalid_claims = {
        "sub": "001234.test",
        "aud": "com.example.newsly",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iat": datetime.now(UTC),
        # Missing "iss" claim
    }

    test_token = jwt.encode(invalid_claims, "dummy-key", algorithm="HS256")

    # Should raise error for missing required claim
    with pytest.raises(ValueError, match="Invalid issuer"):
        verify_apple_token(test_token)
