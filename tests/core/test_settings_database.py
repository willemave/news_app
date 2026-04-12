"""Tests for database URL validation."""

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_settings_reject_sqlite_database_url() -> None:
    """SQLite DSNs should fail with an explicit deprecation error."""
    with pytest.raises(ValidationError, match="SQLite has been deprecated"):
        Settings(
            database_url="sqlite:///tmp/newsly.db",
            JWT_SECRET_KEY="test-secret-key",
            ADMIN_PASSWORD="test-admin-password",
        )
