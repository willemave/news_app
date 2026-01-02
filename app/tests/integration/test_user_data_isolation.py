"""Integration tests for user data isolation."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.schema import Content, ContentFavorites, ContentReadStatus
from app.models.user import User
from app.core.security import create_access_token


def test_users_see_only_their_own_favorites(db_session: Session):
    """Test that users only see their own favorites."""
    from app.core.db import get_db_session, get_readonly_db_session

    # Create two users
    user1 = User(apple_id="user1", email="user1@example.com", is_active=True)
    user2 = User(apple_id="user2", email="user2@example.com", is_active=True)
    db_session.add_all([user1, user2])

    # Create content
    content1 = Content(
        content_type="article",
        url="https://example.com/article1",
        title="Article 1",
        status="completed",
        content_metadata={}
    )
    content2 = Content(
        content_type="article",
        url="https://example.com/article2",
        title="Article 2",
        status="completed",
        content_metadata={}
    )
    db_session.add_all([content1, content2])
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)
    db_session.refresh(content1)
    db_session.refresh(content2)

    # User 1 favorites content 1
    favorite1 = ContentFavorites(user_id=user1.id, content_id=content1.id)
    # User 2 favorites content 2
    favorite2 = ContentFavorites(user_id=user2.id, content_id=content2.id)
    db_session.add_all([favorite1, favorite2])
    db_session.commit()

    # Override dependencies for user1
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_readonly_db_session] = override_get_db

    try:
        client = TestClient(app)

        # User 1 should see content1 as favorited, content2 as not favorited
        from app.core.deps import get_current_user

        def override_get_current_user_1():
            return user1

        app.dependency_overrides[get_current_user] = override_get_current_user_1

        token1 = create_access_token(user1.id)
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.get(f"/api/content/{content1.id}", headers=headers1)
        assert response.status_code == 200
        assert response.json()["is_favorited"] is True

        response = client.get(f"/api/content/{content2.id}", headers=headers1)
        assert response.status_code == 200
        assert response.json()["is_favorited"] is False

        # User 2 should see content2 as favorited, content1 as not favorited
        def override_get_current_user_2():
            return user2

        app.dependency_overrides[get_current_user] = override_get_current_user_2

        token2 = create_access_token(user2.id)
        headers2 = {"Authorization": f"Bearer {token2}"}

        response = client.get(f"/api/content/{content1.id}", headers=headers2)
        assert response.status_code == 200
        assert response.json()["is_favorited"] is False

        response = client.get(f"/api/content/{content2.id}", headers=headers2)
        assert response.status_code == 200
        assert response.json()["is_favorited"] is True
    finally:
        app.dependency_overrides.clear()


def test_users_see_only_their_own_read_status(db_session: Session):
    """Test that users only see their own read status."""
    from app.core.db import get_db_session, get_readonly_db_session

    # Create two users
    user1 = User(apple_id="user1_read", email="user1_read@example.com", is_active=True)
    user2 = User(apple_id="user2_read", email="user2_read@example.com", is_active=True)
    db_session.add_all([user1, user2])

    # Create content
    content = Content(
        content_type="article",
        url="https://example.com/article_read",
        title="Article for Read Test",
        status="completed",
        content_metadata={}
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)
    db_session.refresh(content)

    # User 1 marks as read
    read_status = ContentReadStatus(user_id=user1.id, content_id=content.id)
    db_session.add(read_status)
    db_session.commit()

    # Override dependencies
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_readonly_db_session] = override_get_db

    try:
        client = TestClient(app)

        # User 1 should see content as read
        from app.core.deps import get_current_user

        def override_get_current_user_1():
            return user1

        app.dependency_overrides[get_current_user] = override_get_current_user_1

        token1 = create_access_token(user1.id)
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.get(f"/api/content/{content.id}", headers=headers1)
        assert response.status_code == 200
        assert response.json()["is_read"] is True

        # User 2 should see content as unread
        def override_get_current_user_2():
            return user2

        app.dependency_overrides[get_current_user] = override_get_current_user_2

        token2 = create_access_token(user2.id)
        headers2 = {"Authorization": f"Bearer {token2}"}

        response = client.get(f"/api/content/{content.id}", headers=headers2)
        assert response.status_code == 200
        assert response.json()["is_read"] is False
    finally:
        app.dependency_overrides.clear()


def test_favorite_action_only_affects_current_user(db_session: Session):
    """Test that favoriting content only affects the current user."""
    from app.core.db import get_db_session, get_readonly_db_session
    from app.core.deps import get_current_user

    # Create two users
    user1 = User(apple_id="user1_fav_action", email="user1_fav@example.com", is_active=True)
    user2 = User(apple_id="user2_fav_action", email="user2_fav@example.com", is_active=True)
    db_session.add_all([user1, user2])

    # Create content
    content = Content(
        content_type="article",
        url="https://example.com/fav_action",
        title="Favorite Action Test",
        status="completed",
        content_metadata={}
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(user1)
    db_session.refresh(user2)
    db_session.refresh(content)

    # Override dependencies
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db_session] = override_get_db
    app.dependency_overrides[get_readonly_db_session] = override_get_db

    try:
        client = TestClient(app)

        # User 1 favorites the content
        def override_get_current_user_1():
            return user1

        app.dependency_overrides[get_current_user] = override_get_current_user_1

        token1 = create_access_token(user1.id)
        headers1 = {"Authorization": f"Bearer {token1}"}

        response = client.post(f"/api/content/{content.id}/favorite", headers=headers1)
        assert response.status_code == 200
        assert response.json()["is_favorited"] is True

        # User 2 should still see it as not favorited
        def override_get_current_user_2():
            return user2

        app.dependency_overrides[get_current_user] = override_get_current_user_2

        token2 = create_access_token(user2.id)
        headers2 = {"Authorization": f"Bearer {token2}"}

        response = client.get(f"/api/content/{content.id}", headers=headers2)
        assert response.status_code == 200
        assert response.json()["is_favorited"] is False
    finally:
        app.dependency_overrides.clear()
