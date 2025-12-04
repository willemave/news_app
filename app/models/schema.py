import enum
from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import validates

from app.core.db import Base
from app.core.logging import get_logger
from app.models.metadata import (
    ContentStatus,
    StructuredSummary,
    validate_content_metadata,
)
from app.models.user import User  # noqa: F401

logger = get_logger(__name__)


class Content(Base):
    __tablename__ = "contents"

    # Primary fields
    id = Column(Integer, primary_key=True)
    content_type = Column(String(20), nullable=False, index=True)
    url = Column(String(2048), nullable=False)
    title = Column(String(500), nullable=True)
    source = Column(String(100), nullable=True, index=True)
    platform = Column(String(50), nullable=True, index=True)
    is_aggregate = Column(Boolean, default=False, nullable=False, index=True)

    # Status tracking
    status = Column(String(20), default=ContentStatus.NEW.value, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    # Classification
    classification = Column(String(20), nullable=True, index=True)

    # Checkout mechanism
    checked_out_by = Column(String(100), nullable=True, index=True)
    checked_out_at = Column(DateTime, nullable=True)

    # Type-specific data stored as JSON
    # For articles: author, content, publish_date, source, internal_links
    # For podcasts: audio_url, transcript, duration, episode_number
    content_metadata = Column(JSON, default=dict, nullable=False)

    # Common timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    publication_date = Column(DateTime, nullable=True, index=True)

    # Indexes for performance
    __table_args__ = (
        Index("idx_content_type_status", "content_type", "status"),
        Index("idx_checkout", "checked_out_by", "checked_out_at"),
        Index("idx_created_at", "created_at"),
        Index("idx_content_aggregate", "content_type", "is_aggregate"),
        Index("idx_url_content_type", "url", "content_type", unique=True),
    )

    @validates("content_metadata")
    def validate_metadata(self, key, value):
        """Validate metadata using Pydantic models."""
        if not value or value == {}:
            return value

        # Skip validation during initial load or if content_type not set
        if not hasattr(self, "content_type") or not self.content_type:
            return value

        try:
            # Validate using appropriate schema
            validated = validate_content_metadata(self.content_type, value)
            # Convert back to dict for storage, excluding None values to preserve original data
            return validated.model_dump(mode="json", exclude_none=True)
        except ValidationError as e:
            logger.warning(f"Metadata validation failed for {self.content_type}: {e}")
            # For backward compatibility, store as-is but log warning
            return value
        except Exception as e:
            logger.error(f"Unexpected error validating metadata: {e}")
            return value

    def get_validated_metadata(self) -> dict[str, Any] | None:
        """Get metadata as validated Pydantic model."""
        if not self.content_metadata:
            return None

        try:
            return validate_content_metadata(self.content_type, self.content_metadata)
        except Exception as e:
            logger.error(f"Error validating metadata for content {self.id}: {e}")
            return None

    def get_structured_summary(self) -> StructuredSummary | None:
        """Get structured summary if available."""
        if not self.content_metadata:
            return None

        summary = self.content_metadata.get("summary")
        if not summary:
            return None

        # Check if it's already a structured summary
        if isinstance(summary, dict) and "bullet_points" in summary:
            try:
                return StructuredSummary(**summary)
            except Exception as e:
                logger.error(f"Error parsing structured summary: {e}")

        return None


class ProcessingTask(Base):
    """Simple task queue to replace Huey"""

    __tablename__ = "processing_tasks"

    id = Column(Integer, primary_key=True)
    task_type = Column(String(50), nullable=False, index=True)
    content_id = Column(Integer, nullable=True, index=True)
    payload = Column(JSON, default=dict)
    status = Column(String(20), default="pending", index=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)

    __table_args__ = (Index("idx_task_status_created", "status", "created_at"),)


class ContentReadStatus(Base):
    """Track which content has been read by which user."""

    __tablename__ = "content_read_status"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    content_id = Column(Integer, nullable=False, index=True)
    read_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (Index("idx_content_read_user_content", "user_id", "content_id", unique=True),)


class ContentFavorites(Base):
    """Track which content has been favorited by which user."""

    __tablename__ = "content_favorites"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    content_id = Column(Integer, nullable=False, index=True)
    favorited_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_content_favorites_user_content", "user_id", "content_id", unique=True),
    )


class ContentUnlikes(Base):
    """Track which content has been unliked by which user."""

    __tablename__ = "content_unlikes"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    content_id = Column(Integer, nullable=False, index=True)
    unliked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("idx_content_unlikes_user_content", "user_id", "content_id", unique=True),
    )


class EventLog(Base):
    """Generic event logging table for all system events, stats, and errors."""

    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True)
    # Examples: 'scraper_run', 'processing_batch', 'error', 'cleanup'
    event_type = Column(String(50), nullable=False, index=True)
    # Examples: 'hackernews_scraper', 'pdf_processor'
    event_name = Column(String(100), nullable=True, index=True)
    status = Column(String(20), nullable=True, index=True)  # 'started', 'completed', 'failed'

    # All data stored in one JSON field - completely flexible
    data = Column(JSON, nullable=False, default=dict)

    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("idx_event_type_created", "event_type", "created_at"),
        Index("idx_event_name_created", "event_name", "created_at"),
        Index("idx_event_status_created", "event_type", "status", "created_at"),
    )


class ContentStatusEntry(Base):
    """Per-user status for content feed membership."""

    __tablename__ = "content_status"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    content_id = Column(Integer, nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True, default="inbox")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "content_id", name="idx_content_status_user_content"),
    )


class UserScraperConfig(Base):
    """Per-user scraper configuration for dynamic sources."""

    __tablename__ = "user_scraper_configs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    scraper_type = Column(String(50), nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    feed_url = Column(String(2048), nullable=True)
    config = Column(JSON, default=dict, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "scraper_type", "feed_url", name="uq_user_scraper_feed"),
        Index("idx_user_scraper_user_type", "user_id", "scraper_type"),
    )


class ChatSession(Base):
    """Chat session for deep-dive conversations with articles/news."""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    content_id = Column(Integer, nullable=True, index=True)  # soft ref to contents.id
    title = Column(String(500), nullable=True)
    session_type = Column(String(50), nullable=True)  # article_brain, topic, ad_hoc
    topic = Column(String(500), nullable=True)
    llm_model = Column(String(100), nullable=False, default="openai:gpt-5.1")
    llm_provider = Column(String(50), nullable=False, default="openai")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True, index=True)
    is_archived = Column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("idx_chat_sessions_user_time", "user_id", "last_message_at"),
        Index("idx_chat_sessions_content", "user_id", "content_id"),
    )


class MessageProcessingStatus(str, enum.Enum):
    """Processing status for async chat messages."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatMessage(Base):
    """Chat message history stored as pydantic-ai ModelMessage JSON."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, nullable=False, index=True)  # soft ref to chat_sessions.id
    message_list = Column(Text, nullable=False)  # JSON from ModelMessagesTypeAdapter
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    # Async processing fields
    status = Column(
        String(20),
        nullable=False,
        default=MessageProcessingStatus.COMPLETED.value,
        index=True,
    )
    error = Column(Text, nullable=True)  # Error message if status=failed

    __table_args__ = (Index("idx_chat_messages_session_created", "session_id", "created_at"),)
