"""Tests for authentication endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.user import User

client = TestClient(app)


def test_apple_signin_new_user(db: Session, monkeypatch):
    """Test Apple Sign In creates new user."""
    # Override get_db to use our test db
    from app.core.db import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Mock Apple token verification
    def mock_verify_apple_token(id_token):
        return {
            "sub": "001234.abcd1234",
            "email": "newuser@icloud.com",
            "email_verified": True
        }

    monkeypatch.setattr("app.routers.auth.verify_apple_token", mock_verify_apple_token)

    try:
        response = client.post(
            "/auth/apple",
            json={
                "id_token": "mock.apple.token",
                "email": "newuser@icloud.com",
                "full_name": "New User"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "newuser@icloud.com"
        assert data["user"]["full_name"] == "New User"
    finally:
        app.dependency_overrides.clear()


def test_apple_signin_existing_user(db: Session, monkeypatch):
    """Test Apple Sign In with existing user."""
    # Override get_db to use our test db
    from app.core.db import get_db

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Create existing user
    existing_user = User(
        apple_id="001234.existing",
        email="existing@icloud.com",
        full_name="Existing User"
    )
    db.add(existing_user)
    db.commit()
    db.refresh(existing_user)

    # Mock Apple token verification
    def mock_verify_apple_token(id_token):
        return {
            "sub": "001234.existing",
            "email": "existing@icloud.com"
        }

    monkeypatch.setattr("app.routers.auth.verify_apple_token", mock_verify_apple_token)

    try:
        response = client.post(
            "/auth/apple",
            json={
                "id_token": "mock.apple.token",
                "email": "existing@icloud.com"
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["user"]["id"] == existing_user.id
        assert data["user"]["email"] == "existing@icloud.com"
    finally:
        app.dependency_overrides.clear()


def test_apple_signin_invalid_token(monkeypatch):
    """Test Apple Sign In with invalid token."""
    # Mock Apple token verification to raise error
    def mock_verify_apple_token(id_token):
        raise ValueError("Invalid token")

    monkeypatch.setattr("app.routers.auth.verify_apple_token", mock_verify_apple_token)

    response = client.post(
        "/auth/apple",
        json={
            "id_token": "invalid.token",
            "email": "test@icloud.com"
        }
    )

    assert response.status_code == 401
    assert "Invalid Apple token" in response.json()["detail"]
