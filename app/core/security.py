"""Security utilities for authentication."""
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from authlib.jose import JsonWebToken
from authlib.jose.errors import JoseError

from app.core.settings import get_settings


def create_token(user_id: int, token_type: str, expires_delta: timedelta) -> str:
    """
    Create a JWT token.

    Args:
        user_id: User ID to encode in token
        token_type: Type of token ('access' or 'refresh')
        expires_delta: Time until token expires

    Returns:
        Encoded JWT token string
    """
    settings = get_settings()

    expire = datetime.now(UTC) + expires_delta
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(UTC),
    }

    encoded_jwt = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def create_access_token(user_id: int) -> str:
    """
    Create an access token with configured expiry.

    Args:
        user_id: User ID to encode in token

    Returns:
        JWT access token
    """
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(user_id, "access", expires_delta)


def create_refresh_token(user_id: int) -> str:
    """
    Create a refresh token with configured expiry.

    Args:
        user_id: User ID to encode in token

    Returns:
        JWT refresh token
    """
    settings = get_settings()
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(user_id, "refresh", expires_delta)


def verify_token(token: str) -> dict[str, Any]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload

    Raises:
        jwt.ExpiredSignatureError: If token is expired
        jwt.InvalidTokenError: If token is invalid
    """
    settings = get_settings()

    payload = jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM]
    )

    return payload


def verify_apple_token(id_token: str) -> dict[str, Any]:
    """
    Verify Apple identity token.

    Args:
        id_token: Apple identity token from Sign in with Apple

    Returns:
        Decoded token claims

    Raises:
        JoseError: If token verification fails

    Note:
        In production, this should fetch Apple's public keys and verify signature.
        For MVP, we'll do basic decoding without signature verification.
        TODO: Implement full verification with Apple's public keys
    """
    try:
        # For MVP: decode without verification (ONLY for development)
        # Production TODO: Verify signature with Apple's public keys
        jwt_instance = JsonWebToken(['RS256'])
        claims = jwt_instance.decode(id_token, None, claims_options={
            "iss": {"essential": True, "value": "https://appleid.apple.com"},
            "aud": {"essential": True},  # Should match your app's bundle ID
        })

        return dict(claims)
    except JoseError as e:
        raise ValueError(f"Invalid Apple token: {str(e)}") from e


def verify_admin_password(password: str) -> bool:
    """
    Verify admin password against environment variable.

    Args:
        password: Password to verify

    Returns:
        True if password matches, False otherwise
    """
    settings = get_settings()
    return password == settings.ADMIN_PASSWORD
