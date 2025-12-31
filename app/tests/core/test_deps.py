"""Tests for FastAPI dependencies."""
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.deps import DEV_USER_EMAIL, get_current_user
from app.core.security import create_access_token, create_refresh_token
from app.core.settings import get_settings
from app.models.user import User


def test_get_current_user_valid_token(db: Session):
    """Test get_current_user with valid token."""
    # Create test user
    user = User(
        apple_id="test.apple.001",
        email="test@example.com",
        full_name="Test User",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Create valid access token
    token = create_access_token(user.id)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    # Get user from token
    result = get_current_user(credentials=credentials, db=db)

    assert result.id == user.id
    assert result.email == user.email


def test_get_current_user_invalid_token(db: Session):
    """Test get_current_user with invalid token."""
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid.token.here")

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=credentials, db=db)

    assert exc_info.value.status_code == 401
    assert "Could not validate credentials" in str(exc_info.value.detail)


def test_get_current_user_nonexistent_user(db: Session):
    """Test get_current_user with token for non-existent user."""
    # Create token for user ID that doesn't exist
    token = create_access_token(999999)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=credentials, db=db)

    assert exc_info.value.status_code == 401


def test_get_current_user_inactive_user(db: Session):
    """Test get_current_user with inactive user."""
    # Create inactive user
    user = User(
        apple_id="test.apple.002",
        email="inactive@example.com",
        full_name="Inactive User",
        is_active=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=credentials, db=db)

    assert exc_info.value.status_code == 400
    assert "Inactive user" in str(exc_info.value.detail)


def test_get_current_user_refresh_token(db: Session):
    """Test get_current_user rejects refresh token."""
    # Create user
    user = User(
        apple_id="test.apple.003",
        email="test3@example.com",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Try with refresh token (should fail)
    refresh_token = create_refresh_token(user.id)
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=refresh_token)

    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=credentials, db=db)

    assert exc_info.value.status_code == 401


def test_get_current_user_debug_bypass(db: Session, monkeypatch):
    """Test get_current_user bypasses authentication when debug is enabled."""
    monkeypatch.setenv("DEBUG", "true")
    get_settings.cache_clear()

    try:
        result = get_current_user(credentials=None, db=db)
        assert result.email == DEV_USER_EMAIL
        assert result.is_active is True
    finally:
        monkeypatch.delenv("DEBUG", raising=False)
        get_settings.cache_clear()
