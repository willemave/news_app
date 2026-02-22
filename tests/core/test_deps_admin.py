"""Tests for admin authentication dependency."""

import pytest
from fastapi import Request
from unittest.mock import Mock, MagicMock

from app.core.deps import require_admin, AdminAuthRequired


def test_require_admin_valid_session(monkeypatch):
    """Test require_admin with valid admin session."""
    # Mock admin sessions
    test_session_token = "valid_session_token_123"
    mock_admin_sessions = {test_session_token}

    monkeypatch.setattr("app.routers.auth.admin_sessions", mock_admin_sessions)

    # Create mock request with valid session cookie
    mock_request = Mock(spec=Request)
    mock_request.cookies = {"admin_session": test_session_token}

    # Create mock db session
    mock_db = MagicMock()
    mock_admin_user = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_admin_user

    # Should not raise, should return admin user
    result = require_admin(mock_request, mock_db)
    assert result == mock_admin_user


def test_require_admin_no_cookie():
    """Test require_admin without session cookie."""
    mock_request = Mock(spec=Request)
    mock_request.cookies = {}
    mock_request.url.path = "/admin/dashboard"

    mock_db = MagicMock()

    with pytest.raises(AdminAuthRequired) as exc_info:
        require_admin(mock_request, mock_db)

    assert "/auth/admin/login" in exc_info.value.redirect_url


def test_require_admin_invalid_session(monkeypatch):
    """Test require_admin with invalid session token."""
    mock_admin_sessions = {"valid_token"}
    monkeypatch.setattr("app.routers.auth.admin_sessions", mock_admin_sessions)

    mock_request = Mock(spec=Request)
    mock_request.cookies = {"admin_session": "invalid_token"}
    mock_request.url.path = "/admin/dashboard"

    mock_db = MagicMock()

    with pytest.raises(AdminAuthRequired) as exc_info:
        require_admin(mock_request, mock_db)

    assert "/auth/admin/login" in exc_info.value.redirect_url


def test_require_admin_expired_session(monkeypatch):
    """Test require_admin after session has been removed."""
    # Session was valid but has been logged out
    mock_admin_sessions = set()
    monkeypatch.setattr("app.routers.auth.admin_sessions", mock_admin_sessions)

    mock_request = Mock(spec=Request)
    mock_request.cookies = {"admin_session": "expired_token"}
    mock_request.url.path = "/admin/dashboard"

    mock_db = MagicMock()

    with pytest.raises(AdminAuthRequired) as exc_info:
        require_admin(mock_request, mock_db)

    assert "/auth/admin/login" in exc_info.value.redirect_url
