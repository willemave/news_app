"""Integration tests for authentication on protected endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.schema import Content
from app.models.user import User
from app.core.security import create_access_token


def test_api_endpoints_require_authentication():
    """Test that API endpoints reject requests without authentication."""
    client = TestClient(app)

    # Test core authenticated endpoints
    endpoints_to_test = [
        ("GET", "/api/content/"),
        ("GET", "/api/content/1"),
        ("POST", "/api/content/1/favorite"),
        ("POST", "/api/content/1/mark-read"),
    ]

    for method, endpoint in endpoints_to_test:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint)

        # FastAPI's HTTPBearer returns 403 when no credentials provided, 401 for invalid credentials
        assert response.status_code in [401, 403], f"{method} {endpoint} should require auth (got {response.status_code})"


def test_authenticated_requests_accepted(db_session: Session):
    """Test that authenticated requests are accepted."""
    from app.core.db import get_db_session
    from app.core.deps import get_current_user

    # Create test user
    user = User(
        apple_id="test.integration.001",
        email="integration@example.com",
        is_active=True
    )
    db_session.add(user)

    # Create test content with valid metadata
    content = Content(
        content_type="article",
        url="https://example.com/test",
        title="Test Article",
        status="completed",
        content_metadata={}
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(content)

    # Override dependencies
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_current_user():
        return user

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    try:
        client = TestClient(app)
        token = create_access_token(user.id)
        headers = {"Authorization": f"Bearer {token}"}

        # These should all succeed now
        response = client.get("/api/content/", headers=headers)
        assert response.status_code == 200

        response = client.get(f"/api/content/{content.id}", headers=headers)
        assert response.status_code == 200

        response = client.post(f"/api/content/{content.id}/favorite", headers=headers)
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_invalid_token_rejected():
    """Test that requests with invalid tokens are rejected."""
    client = TestClient(app)
    headers = {"Authorization": "Bearer invalid.token.here"}

    response = client.get("/api/content/", headers=headers)
    assert response.status_code == 401


def test_expired_token_rejected(db_session: Session):
    """Test that expired tokens are rejected."""
    from app.core.security import create_token
    from datetime import timedelta

    # Create user
    user = User(
        apple_id="test.expired.001",
        email="expired@example.com",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Create expired token
    expired_token = create_token(user.id, "access", timedelta(hours=-1))

    client = TestClient(app)
    headers = {"Authorization": f"Bearer {expired_token}"}

    response = client.get("/api/content/", headers=headers)
    assert response.status_code == 401
