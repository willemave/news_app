"""Tests for read_status service."""

import pytest
from sqlalchemy.orm import Session

from app.models.schema import Content, ContentReadStatus, User
from app.services import read_status


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create a test user."""
    user = User(
        email="test@example.com",
        apple_id="test_apple_id",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_content(db_session: Session) -> Content:
    """Create test content."""
    content = Content(
        content_type="article",
        url="https://example.com/article",
        title="Test Article",
        source="example.com",
        status="completed",
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


@pytest.fixture
def test_content_2(db_session: Session) -> Content:
    """Create second test content."""
    content = Content(
        content_type="article",
        url="https://example.com/article2",
        title="Test Article 2",
        source="example.com",
        status="completed",
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


@pytest.fixture
def test_content_3(db_session: Session) -> Content:
    """Create third test content."""
    content = Content(
        content_type="article",
        url="https://example.com/article3",
        title="Test Article 3",
        source="example.com",
        status="completed",
    )
    db_session.add(content)
    db_session.commit()
    db_session.refresh(content)
    return content


class TestMarkContentAsRead:
    """Tests for mark_content_as_read function."""

    def test_mark_content_as_read_success(self, db_session: Session, test_user: User, test_content: Content):
        """Test marking content as read successfully."""
        # Act
        result = read_status.mark_content_as_read(db_session, test_content.id, test_user.id)

        # Assert
        assert result is not None
        assert result.content_id == test_content.id
        assert result.user_id == test_user.id
        assert result.read_at is not None

    def test_mark_content_as_read_already_read(self, db_session: Session, test_user: User, test_content: Content):
        """Test marking already read content refreshes timestamp."""
        # Arrange - mark as read first
        first = read_status.mark_content_as_read(db_session, test_content.id, test_user.id)
        first_timestamp = first.read_at

        # Act - mark as read again
        second = read_status.mark_content_as_read(db_session, test_content.id, test_user.id)

        # Assert - should return same record with updated timestamp
        assert second is not None
        assert first.id == second.id
        assert second.read_at >= first_timestamp

    def test_mark_content_as_read_user_isolation(self, db_session: Session, test_content: Content):
        """Test that read status is isolated per user."""
        # Arrange - create two users
        user1 = User(email="user1@example.com", apple_id="apple_id_1", is_active=True)
        user2 = User(email="user2@example.com", apple_id="apple_id_2", is_active=True)
        db_session.add_all([user1, user2])
        db_session.commit()

        # Act - user1 marks as read
        read_status.mark_content_as_read(db_session, test_content.id, user1.id)

        # Assert - user1 has read, user2 has not
        assert read_status.is_content_read(db_session, test_content.id, user1.id)
        assert not read_status.is_content_read(db_session, test_content.id, user2.id)


class TestMarkContentsAsRead:
    """Tests for mark_contents_as_read function."""

    def test_mark_contents_as_read_empty_list(self, db_session: Session, test_user: User):
        """Test marking empty list returns zero."""
        # Act
        marked_count, failed_ids = read_status.mark_contents_as_read(db_session, [], test_user.id)

        # Assert
        assert marked_count == 0
        assert failed_ids == []

    def test_mark_contents_as_read_multiple(
        self, db_session: Session, test_user: User, test_content: Content, test_content_2: Content, test_content_3: Content
    ):
        """Test marking multiple contents as read."""
        # Act
        content_ids = [test_content.id, test_content_2.id, test_content_3.id]
        marked_count, failed_ids = read_status.mark_contents_as_read(db_session, content_ids, test_user.id)

        # Assert
        assert marked_count == 3
        assert failed_ids == []
        assert read_status.is_content_read(db_session, test_content.id, test_user.id)
        assert read_status.is_content_read(db_session, test_content_2.id, test_user.id)
        assert read_status.is_content_read(db_session, test_content_3.id, test_user.id)

    def test_mark_contents_as_read_with_duplicates(self, db_session: Session, test_user: User, test_content: Content):
        """Test marking contents with duplicate IDs."""
        # Act
        content_ids = [test_content.id, test_content.id, test_content.id]
        marked_count, failed_ids = read_status.mark_contents_as_read(db_session, content_ids, test_user.id)

        # Assert
        assert marked_count == 1  # Only one unique ID
        assert failed_ids == []

    def test_mark_contents_as_read_partial_already_read(
        self, db_session: Session, test_user: User, test_content: Content, test_content_2: Content
    ):
        """Test marking contents when some are already read."""
        # Arrange - mark one as read first
        read_status.mark_content_as_read(db_session, test_content.id, test_user.id)

        # Act - mark both
        content_ids = [test_content.id, test_content_2.id]
        marked_count, failed_ids = read_status.mark_contents_as_read(db_session, content_ids, test_user.id)

        # Assert
        assert marked_count == 2
        assert failed_ids == []

    def test_mark_contents_as_read_user_isolation(
        self, db_session: Session, test_content: Content, test_content_2: Content
    ):
        """Test that bulk marking is isolated per user."""
        # Arrange - create two users
        user1 = User(email="user1@example.com", apple_id="apple_id_1", is_active=True)
        user2 = User(email="user2@example.com", apple_id="apple_id_2", is_active=True)
        db_session.add_all([user1, user2])
        db_session.commit()

        # Act - user1 marks content1, user2 marks content2
        read_status.mark_contents_as_read(db_session, [test_content.id], user1.id)
        read_status.mark_contents_as_read(db_session, [test_content_2.id], user2.id)

        # Assert
        user1_read = read_status.get_read_content_ids(db_session, user1.id)
        user2_read = read_status.get_read_content_ids(db_session, user2.id)
        assert user1_read == [test_content.id]
        assert user2_read == [test_content_2.id]


class TestGetReadContentIds:
    """Tests for get_read_content_ids function."""

    def test_get_read_content_ids_empty(self, db_session: Session, test_user: User):
        """Test getting read IDs when user has read nothing."""
        # Act
        content_ids = read_status.get_read_content_ids(db_session, test_user.id)

        # Assert
        assert content_ids == []

    def test_get_read_content_ids_multiple(
        self, db_session: Session, test_user: User, test_content: Content, test_content_2: Content
    ):
        """Test getting read IDs when user has read multiple items."""
        # Arrange - mark as read
        read_status.mark_content_as_read(db_session, test_content.id, test_user.id)
        read_status.mark_content_as_read(db_session, test_content_2.id, test_user.id)

        # Act
        content_ids = read_status.get_read_content_ids(db_session, test_user.id)

        # Assert
        assert len(content_ids) == 2
        assert test_content.id in content_ids
        assert test_content_2.id in content_ids

    def test_get_read_content_ids_user_isolation(
        self, db_session: Session, test_content: Content, test_content_2: Content
    ):
        """Test that read IDs are isolated per user."""
        # Arrange - create two users with different read content
        user1 = User(email="user1@example.com", apple_id="apple_id_1", is_active=True)
        user2 = User(email="user2@example.com", apple_id="apple_id_2", is_active=True)
        db_session.add_all([user1, user2])
        db_session.commit()

        read_status.mark_content_as_read(db_session, test_content.id, user1.id)
        read_status.mark_content_as_read(db_session, test_content_2.id, user2.id)

        # Act
        user1_read = read_status.get_read_content_ids(db_session, user1.id)
        user2_read = read_status.get_read_content_ids(db_session, user2.id)

        # Assert
        assert user1_read == [test_content.id]
        assert user2_read == [test_content_2.id]


class TestIsContentRead:
    """Tests for is_content_read function."""

    def test_is_content_read_true(self, db_session: Session, test_user: User, test_content: Content):
        """Test checking if content is read returns True when it is."""
        # Arrange
        read_status.mark_content_as_read(db_session, test_content.id, test_user.id)

        # Act
        is_read = read_status.is_content_read(db_session, test_content.id, test_user.id)

        # Assert
        assert is_read is True

    def test_is_content_read_false(self, db_session: Session, test_user: User, test_content: Content):
        """Test checking if content is read returns False when it isn't."""
        # Act
        is_read = read_status.is_content_read(db_session, test_content.id, test_user.id)

        # Assert
        assert is_read is False


class TestClearReadStatus:
    """Tests for clear_read_status function."""

    def test_clear_read_status_success(
        self, db_session: Session, test_user: User, test_content: Content, test_content_2: Content
    ):
        """Test clearing all read status for a user."""
        # Arrange - mark multiple as read
        read_status.mark_content_as_read(db_session, test_content.id, test_user.id)
        read_status.mark_content_as_read(db_session, test_content_2.id, test_user.id)

        # Act
        count = read_status.clear_read_status(db_session, test_user.id)

        # Assert
        assert count == 2
        assert read_status.get_read_content_ids(db_session, test_user.id) == []

    def test_clear_read_status_empty(self, db_session: Session, test_user: User):
        """Test clearing read status when user has none."""
        # Act
        count = read_status.clear_read_status(db_session, test_user.id)

        # Assert
        assert count == 0

    def test_clear_read_status_user_isolation(
        self, db_session: Session, test_content: Content, test_content_2: Content
    ):
        """Test that clearing read status only affects specific user."""
        # Arrange - create two users with read content
        user1 = User(email="user1@example.com", apple_id="apple_id_1", is_active=True)
        user2 = User(email="user2@example.com", apple_id="apple_id_2", is_active=True)
        db_session.add_all([user1, user2])
        db_session.commit()

        read_status.mark_content_as_read(db_session, test_content.id, user1.id)
        read_status.mark_content_as_read(db_session, test_content_2.id, user2.id)

        # Act - clear user1's read status
        read_status.clear_read_status(db_session, user1.id)

        # Assert - user1's cleared, user2's remains
        assert read_status.get_read_content_ids(db_session, user1.id) == []
        assert read_status.get_read_content_ids(db_session, user2.id) == [test_content_2.id]
