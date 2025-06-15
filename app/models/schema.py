from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, Integer, String, DateTime,
    JSON, Index, UniqueConstraint, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import validates
from pydantic import ValidationError

from app.schemas.metadata import (
    validate_content_metadata,
    ArticleMetadata,
    PodcastMetadata,
    StructuredSummary
)
from app.core.logging import get_logger

logger = get_logger(__name__)
Base = declarative_base()

class ContentType(str, Enum):
    ARTICLE = "article"
    PODCAST = "podcast"

class ContentStatus(str, Enum):
    NEW = "new"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class Content(Base):
    __tablename__ = "contents"
    
    # Primary fields
    id = Column(Integer, primary_key=True)
    content_type = Column(String(20), nullable=False, index=True)
    url = Column(String(2048), nullable=False, unique=True)
    title = Column(String(500), nullable=True)
    
    # Status tracking
    status = Column(String(20), default=ContentStatus.NEW.value, nullable=False, index=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Checkout mechanism
    checked_out_by = Column(String(100), nullable=True, index=True)
    checked_out_at = Column(DateTime, nullable=True)
    
    # Type-specific data stored as JSON
    # For articles: author, content, publish_date, source_type, internal_links
    # For podcasts: audio_url, transcript, duration, episode_number
    content_metadata = Column(JSON, default=dict, nullable=False)
    
    # Common timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_content_type_status', 'content_type', 'status'),
        Index('idx_checkout', 'checked_out_by', 'checked_out_at'),
        Index('idx_created_at', 'created_at'),
    )
    
    @validates('content_metadata')
    def validate_metadata(self, key, value):
        """Validate metadata using Pydantic models."""
        if not value or value == {}:
            return value
            
        # Skip validation during initial load or if content_type not set
        if not hasattr(self, 'content_type') or not self.content_type:
            return value
            
        try:
            # Validate using appropriate schema
            validated = validate_content_metadata(self.content_type, value)
            # Convert back to dict for storage
            return validated.model_dump(mode='json')
        except ValidationError as e:
            logger.warning(f"Metadata validation failed for {self.content_type}: {e}")
            # For backward compatibility, store as-is but log warning
            return value
        except Exception as e:
            logger.error(f"Unexpected error validating metadata: {e}")
            return value
    
    def get_validated_metadata(self) -> Optional[Dict[str, Any]]:
        """Get metadata as validated Pydantic model."""
        if not self.content_metadata:
            return None
            
        try:
            return validate_content_metadata(self.content_type, self.content_metadata)
        except Exception as e:
            logger.error(f"Error validating metadata for content {self.id}: {e}")
            return None
    
    def get_structured_summary(self) -> Optional[StructuredSummary]:
        """Get structured summary if available."""
        if not self.content_metadata:
            return None
            
        summary = self.content_metadata.get('summary')
        if not summary:
            return None
            
        # Check if it's already a structured summary
        if isinstance(summary, dict) and 'bullet_points' in summary:
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
    
    __table_args__ = (
        Index('idx_task_status_created', 'status', 'created_at'),
    )