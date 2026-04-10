"""Tests for knowledge-library service helpers."""

from sqlalchemy.orm import Session

from app.models.schema import ChatSession, Content, User
from app.services import knowledge


class TestToggleKnowledgeSave:
    """Tests for toggling knowledge saves."""

    def test_toggle_knowledge_save_adds_new(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Toggling should create a new knowledge save."""
        is_saved_to_knowledge, knowledge_save = knowledge.toggle_knowledge_save(
            db_session,
            test_content.id,
            test_user.id,
        )

        # Assert
        assert is_saved_to_knowledge is True
        assert knowledge_save is not None
        assert knowledge_save.content_id == test_content.id
        assert knowledge_save.user_id == test_user.id
        assert db_session.query(ChatSession).count() == 0

    def test_toggle_knowledge_save_removes_existing(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Toggling should remove an existing knowledge save."""
        knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)

        is_saved_to_knowledge, knowledge_save = knowledge.toggle_knowledge_save(
            db_session,
            test_content.id,
            test_user.id,
        )

        # Assert
        assert is_saved_to_knowledge is False
        assert knowledge_save is None

        # Verify it's actually gone
        assert not knowledge.is_saved_to_knowledge(db_session, test_content.id, test_user.id)

    def test_toggle_knowledge_save_does_not_delete_existing_chat_sessions(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Removing a knowledge save should not delete a pre-existing chat session."""
        knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)
        session = ChatSession(
            user_id=test_user.id,
            content_id=test_content.id,
            title="Existing Knowledge Chat",
            session_type="knowledge_chat",
            llm_model="openai:gpt-5.4",
            llm_provider="openai",
        )
        db_session.add(session)
        db_session.commit()

        is_saved_to_knowledge, knowledge_save = knowledge.toggle_knowledge_save(
            db_session,
            test_content.id,
            test_user.id,
        )

        assert is_saved_to_knowledge is False
        assert knowledge_save is None
        assert (
            db_session.query(ChatSession).filter(ChatSession.id == session.id).one_or_none()
            is not None
        )

    def test_toggle_knowledge_save_user_isolation(
        self,
        db_session: Session,
        test_content: Content,
        user_factory,
    ):
        """Knowledge saves should remain isolated per user."""
        user1 = user_factory(email="user1@example.com", apple_id="apple_id_1")
        user2 = user_factory(email="user2@example.com", apple_id="apple_id_2")

        # Act - user1 saves content
        knowledge.toggle_knowledge_save(db_session, test_content.id, user1.id)

        # Assert - user1 has saved it, user2 has not
        assert knowledge.is_saved_to_knowledge(db_session, test_content.id, user1.id)
        assert not knowledge.is_saved_to_knowledge(db_session, test_content.id, user2.id)


class TestSaveToKnowledge:
    """Tests for creating knowledge saves."""

    def test_save_to_knowledge_success(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Saving to knowledge should create a row."""
        knowledge_save = knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)

        # Assert
        assert knowledge_save is not None
        assert knowledge_save.content_id == test_content.id
        assert knowledge_save.user_id == test_user.id
        assert knowledge_save.saved_at is not None

    def test_save_to_knowledge_returns_existing_row(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Saving again should return the existing row."""
        first = knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)

        # Act - try to add again
        second = knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)

        # Assert - should return the same record
        assert second is not None
        assert first.id == second.id


class TestRemoveFromKnowledge:
    """Tests for removing knowledge saves."""

    def test_remove_from_knowledge_success(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Removing from knowledge should delete the row."""
        knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)

        # Act
        removed = knowledge.remove_from_knowledge(db_session, test_content.id, test_user.id)

        # Assert
        assert removed is True
        assert not knowledge.is_saved_to_knowledge(db_session, test_content.id, test_user.id)

    def test_remove_from_knowledge_not_found(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Removing a missing knowledge save should return False."""
        removed = knowledge.remove_from_knowledge(db_session, test_content.id, test_user.id)

        # Assert
        assert removed is False

    def test_remove_from_knowledge_user_isolation(
        self,
        db_session: Session,
        test_content: Content,
        user_factory,
    ):
        """Removing a knowledge save should only affect the current user."""
        user1 = user_factory(email="user1@example.com", apple_id="apple_id_1")
        user2 = user_factory(email="user2@example.com", apple_id="apple_id_2")

        knowledge.save_to_knowledge(db_session, test_content.id, user1.id)
        knowledge.save_to_knowledge(db_session, test_content.id, user2.id)

        # Act - remove user1's save
        knowledge.remove_from_knowledge(db_session, test_content.id, user1.id)

        # Assert - user1's save removed, user2's remains
        assert not knowledge.is_saved_to_knowledge(db_session, test_content.id, user1.id)
        assert knowledge.is_saved_to_knowledge(db_session, test_content.id, user2.id)


class TestListKnowledgeContentIds:
    """Tests for listing saved knowledge content ids."""

    def test_list_knowledge_content_ids_empty(self, db_session: Session, test_user: User):
        """Listing should return an empty set when nothing is saved."""
        # Act
        content_ids = knowledge.list_knowledge_content_ids(db_session, test_user.id)

        # Assert
        assert content_ids == []

    def test_list_knowledge_content_ids_multiple(
        self, db_session: Session, test_user: User, test_content: Content, test_content_2: Content
    ):
        """Listing should include each saved content id."""
        # Arrange - add knowledge saves
        knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)
        knowledge.save_to_knowledge(db_session, test_content_2.id, test_user.id)

        # Act
        content_ids = knowledge.list_knowledge_content_ids(db_session, test_user.id)

        # Assert
        assert len(content_ids) == 2
        assert test_content.id in content_ids
        assert test_content_2.id in content_ids

    def test_list_knowledge_content_ids_user_isolation(
        self,
        db_session: Session,
        test_content: Content,
        test_content_2: Content,
        user_factory,
    ):
        """Saved content ids should remain isolated per user."""
        user1 = user_factory(email="user1@example.com", apple_id="apple_id_1")
        user2 = user_factory(email="user2@example.com", apple_id="apple_id_2")

        knowledge.save_to_knowledge(db_session, test_content.id, user1.id)
        knowledge.save_to_knowledge(db_session, test_content_2.id, user2.id)

        # Act
        user1_knowledge = knowledge.list_knowledge_content_ids(db_session, user1.id)
        user2_knowledge = knowledge.list_knowledge_content_ids(db_session, user2.id)

        # Assert
        assert user1_knowledge == [test_content.id]
        assert user2_knowledge == [test_content_2.id]


class TestIsSavedToKnowledge:
    """Tests for checking saved-to-knowledge state."""

    def test_is_saved_to_knowledge_true(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Checking saved-to-knowledge should return True when present."""
        knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)

        is_saved_to_knowledge = knowledge.is_saved_to_knowledge(
            db_session,
            test_content.id,
            test_user.id,
        )

        # Assert
        assert is_saved_to_knowledge is True

    def test_is_saved_to_knowledge_false(
        self,
        db_session: Session,
        test_user: User,
        test_content: Content,
    ) -> None:
        """Checking saved-to-knowledge should return False when absent."""
        is_saved_to_knowledge = knowledge.is_saved_to_knowledge(
            db_session,
            test_content.id,
            test_user.id,
        )

        # Assert
        assert is_saved_to_knowledge is False


class TestClearKnowledgeLibrary:
    """Tests for clearing saved knowledge."""

    def test_clear_knowledge_library_success(
        self, db_session: Session, test_user: User, test_content: Content, test_content_2: Content
    ):
        """Clearing should remove every knowledge save for the user."""
        # Arrange - add multiple knowledge saves
        knowledge.save_to_knowledge(db_session, test_content.id, test_user.id)
        knowledge.save_to_knowledge(db_session, test_content_2.id, test_user.id)

        # Act
        count = knowledge.clear_knowledge_library(db_session, test_user.id)

        # Assert
        assert count == 2
        assert knowledge.list_knowledge_content_ids(db_session, test_user.id) == []

    def test_clear_knowledge_library_empty(self, db_session: Session, test_user: User):
        """Clearing should return zero when nothing is saved."""
        # Act
        count = knowledge.clear_knowledge_library(db_session, test_user.id)

        # Assert
        assert count == 0

    def test_clear_knowledge_library_user_isolation(
        self,
        db_session: Session,
        test_content: Content,
        test_content_2: Content,
        user_factory,
    ):
        """Clearing should only affect the selected user's saves."""
        user1 = user_factory(email="user1@example.com", apple_id="apple_id_1")
        user2 = user_factory(email="user2@example.com", apple_id="apple_id_2")

        knowledge.save_to_knowledge(db_session, test_content.id, user1.id)
        knowledge.save_to_knowledge(db_session, test_content_2.id, user2.id)

        # Act - clear user1's saved knowledge
        knowledge.clear_knowledge_library(db_session, user1.id)

        # Assert - user1's saves cleared, user2's remain
        assert knowledge.list_knowledge_content_ids(db_session, user1.id) == []
        assert knowledge.list_knowledge_content_ids(db_session, user2.id) == [test_content_2.id]
