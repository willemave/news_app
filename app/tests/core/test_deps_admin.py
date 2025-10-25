"""Tests for admin authentication dependency."""
import pytest
from fastapi import HTTPException, Request
from unittest.mock import Mock

from app.core.deps import require_admin


def test_require_admin_valid_session(monkeypatch):
    """Test require_admin with valid admin session."""
    # Mock admin sessions
    test_session_token = "valid_session_token_123"
    mock_admin_sessions = {test_session_token}

    monkeypatch.setattr("app.routers.auth.admin_sessions", mock_admin_sessions)

    # Create mock request with valid session cookie
    mock_request = Mock(spec=Request)
    mock_request.cookies = {"admin_session": test_session_token}

    # Should not raise
    require_admin(mock_request)


def test_require_admin_no_cookie():
    """Test require_admin without session cookie."""
    mock_request = Mock(spec=Request)
    mock_request.cookies = {}

    with pytest.raises(HTTPException) as exc_info:
        require_admin(mock_request)

    assert exc_info.value.status_code == 401
    assert "Admin authentication required" in str(exc_info.value.detail)


def test_require_admin_invalid_session(monkeypatch):
    """Test require_admin with invalid session token."""
    mock_admin_sessions = {"valid_token"}
    monkeypatch.setattr("app.routers.auth.admin_sessions", mock_admin_sessions)

    mock_request = Mock(spec=Request)
    mock_request.cookies = {"admin_session": "invalid_token"}

    with pytest.raises(HTTPException) as exc_info:
        require_admin(mock_request)

    assert exc_info.value.status_code == 401


def test_require_admin_expired_session(monkeypatch):
    """Test require_admin after session has been removed."""
    # Session was valid but has been logged out
    mock_admin_sessions = set()
    monkeypatch.setattr("app.routers.auth.admin_sessions", mock_admin_sessions)

    mock_request = Mock(spec=Request)
    mock_request.cookies = {"admin_session": "expired_token"}

    with pytest.raises(HTTPException) as exc_info:
        require_admin(mock_request)

    assert exc_info.value.status_code == 401
