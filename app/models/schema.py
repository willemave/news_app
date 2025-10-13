from datetime import datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy import JSON, Boolean, Column, DateTime, Index, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import validates

from app.core.logging import get_logger
from app.models.metadata import (
    ContentStatus,
    StructuredSummary,
    validate_content_metadata,
)

logger = get_logger(__name__)
Base = declarative_base()


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
    """Track which content has been read by which session."""
    
    __tablename__ = "content_read_status"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    content_id = Column(Integer, nullable=False, index=True)
    read_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_content_read_session_content", "session_id", "content_id", unique=True),
    )


class ContentFavorites(Base):
    """Track which content has been favorited by which session."""
    
    __tablename__ = "content_favorites"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    content_id = Column(Integer, nullable=False, index=True)
    favorited_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_content_favorites_session_content", "session_id", "content_id", unique=True),
    )


class ContentUnlikes(Base):
    """Track which content has been unliked by which session."""
    
    __tablename__ = "content_unlikes"
    
    id = Column(Integer, primary_key=True)
    session_id = Column(String(255), nullable=False, index=True)
    content_id = Column(Integer, nullable=False, index=True)
    unliked_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        Index("idx_content_unlikes_session_content", "session_id", "content_id", unique=True),
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
