"""Tests for content interaction analytics service."""

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema import AnalyticsInteraction, Content
from app.models.user import User
from app.services.content_interactions import (
    INTERACTION_TYPE_OPENED,
    ContentInteractionContentNotFoundError,
    RecordContentInteractionInput,
    record_content_interaction,
)


@pytest.fixture
def analytics_user(db_session: Session) -> User:
    """Create a user for analytics interaction tests."""
    user = User(
        email="analytics-user@example.com",
        apple_id="analytics_user_apple_id",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def analytics_content(db_session: Session) -> Content:
    """Create content for analytics interaction tests."""
    content = Content(
        content_type="article",
        url="https://example.com/analytics-service-content",
        title="Analytics Service Content",
        status="completed",
        content_metadata={},
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


def test_record_content_interaction_success(
    db_session: Session,
    analytics_user: User,
    analytics_content: Content,
) -> None:
    """It should insert a new analytics interaction row."""
    interaction_id = str(uuid4())
    result = record_content_interaction(
        db_session,
        RecordContentInteractionInput(
            user_id=analytics_user.id,
            content_id=analytics_content.id,
            interaction_id=interaction_id,
            interaction_type=INTERACTION_TYPE_OPENED,
            surface="ios_content_detail",
            context_data={"content_type": "article"},
        ),
    )

    assert result.recorded is True
    assert result.interaction_id == interaction_id
    assert result.analytics_interaction_id is not None

    stored = db_session.execute(select(AnalyticsInteraction)).scalars().all()
    assert len(stored) == 1
    assert stored[0].user_id == analytics_user.id
    assert stored[0].content_id == analytics_content.id
    assert stored[0].interaction_id == interaction_id


def test_record_content_interaction_idempotent_for_same_user(
    db_session: Session,
    analytics_user: User,
    analytics_content: Content,
) -> None:
    """It should treat duplicate interaction_id for the same user as idempotent."""
    interaction_id = str(uuid4())
    payload = RecordContentInteractionInput(
        user_id=analytics_user.id,
        content_id=analytics_content.id,
        interaction_id=interaction_id,
        interaction_type=INTERACTION_TYPE_OPENED,
        surface="ios_content_detail",
    )

    first = record_content_interaction(db_session, payload)
    second = record_content_interaction(db_session, payload)

    assert first.recorded is True
    assert second.recorded is False
    assert first.analytics_interaction_id == second.analytics_interaction_id

    stored = db_session.execute(
        select(AnalyticsInteraction).where(AnalyticsInteraction.user_id == analytics_user.id)
    ).scalars()
    assert len(list(stored)) == 1


def test_record_content_interaction_same_interaction_id_for_different_users(
    db_session: Session,
    analytics_content: Content,
) -> None:
    """It should allow the same interaction_id across different users."""
    first_user = User(
        email="analytics-first@example.com",
        apple_id="analytics_first_apple_id",
        is_active=True,
    )
    second_user = User(
        email="analytics-second@example.com",
        apple_id="analytics_second_apple_id",
        is_active=True,
    )
    db_session.add_all([first_user, second_user])
    db_session.commit()
    db_session.refresh(first_user)
    db_session.refresh(second_user)

    interaction_id = str(uuid4())
    first = record_content_interaction(
        db_session,
        RecordContentInteractionInput(
            user_id=first_user.id,
            content_id=analytics_content.id,
            interaction_id=interaction_id,
            interaction_type=INTERACTION_TYPE_OPENED,
        ),
    )
    second = record_content_interaction(
        db_session,
        RecordContentInteractionInput(
            user_id=second_user.id,
            content_id=analytics_content.id,
            interaction_id=interaction_id,
            interaction_type=INTERACTION_TYPE_OPENED,
        ),
    )

    assert first.recorded is True
    assert second.recorded is True
    assert first.analytics_interaction_id != second.analytics_interaction_id


def test_record_content_interaction_raises_for_missing_content(
    db_session: Session,
    analytics_user: User,
) -> None:
    """It should raise a not-found error when content does not exist."""
    with pytest.raises(ContentInteractionContentNotFoundError):
        record_content_interaction(
            db_session,
            RecordContentInteractionInput(
                user_id=analytics_user.id,
                content_id=9_999_999,
                interaction_id=str(uuid4()),
                interaction_type=INTERACTION_TYPE_OPENED,
            ),
        )
