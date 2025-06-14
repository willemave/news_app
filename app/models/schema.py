from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, Integer, String, DateTime,
    JSON, Index, UniqueConstraint, Text
)
from sqlalchemy.ext.declarative import declarative_base

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