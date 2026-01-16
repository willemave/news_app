"""Tests for recently read content endpoints."""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content, ContentFavorites, ContentReadStatus
from app.models.user import User


def test_recently_read_scoped_to_user(client, db_session: Session, test_user: User) -> None:
    """Ensure recently read list only includes the current user's reads."""
    other_user = User(
        apple_id="other_apple_id",
        email="other@example.com",
        full_name="Other User",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    content_one = Content(
        url="https://example.com/read-by-current",
        title="Read by Current User",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )
    content_two = Content(
        url="https://example.com/read-by-other",
        title="Read by Other User",
        content_type=ContentType.ARTICLE.value,
        status=ContentStatus.COMPLETED.value,
        content_metadata={},
    )
    db_session.add_all([content_one, content_two])
    db_session.commit()
    db_session.refresh(content_one)
    db_session.refresh(content_two)

    timestamp = datetime.utcnow()
    db_session.add_all(
        [
            ContentReadStatus(
                user_id=test_user.id,
                content_id=content_one.id,
                read_at=timestamp,
                created_at=timestamp,
            ),
            ContentReadStatus(
                user_id=other_user.id,
                content_id=content_two.id,
                read_at=timestamp,
                created_at=timestamp,
            ),
            ContentFavorites(
                user_id=other_user.id,
                content_id=content_one.id,
                favorited_at=timestamp,
                created_at=timestamp,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/content/recently-read/list")
    assert response.status_code == 200

    payload = response.json()
    ids = {item["id"] for item in payload["contents"]}
    assert content_one.id in ids
    assert content_two.id not in ids

    item = next(entry for entry in payload["contents"] if entry["id"] == content_one.id)
    assert item["is_read"] is True
    assert item["is_favorited"] is False
