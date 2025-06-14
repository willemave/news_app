from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from pydantic import BaseModel, HttpUrl, Field, field_validator


class CustomBaseModel(BaseModel):
    """Custom base model with shared configuration."""
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None,
        }
        
class ContentType(str, Enum):
    ARTICLE = "article"
    PODCAST = "podcast"

class ContentStatus(str, Enum):
    NEW = "new"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class ProcessingResult(BaseModel):
    """Result from content processing."""
    success: bool
    content_type: ContentType
    title: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    internal_links: List[str] = Field(default_factory=list)
    
    class Config:
        frozen = True

class ArticleMetadata(CustomBaseModel):
    """Article-specific metadata."""
    author: Optional[str] = None
    content: Optional[str] = None
    publish_date: Optional[datetime] = None
    source_type: Optional[str] = None
    word_count: Optional[int] = None
    reading_time_minutes: Optional[int] = None
    
    @field_validator("content")
    @classmethod
    def validate_content_length(cls, v):
        if v and len(v) > 1_000_000:  # 1MB limit
            raise ValueError("Content too long")
        return v

class PodcastMetadata(CustomBaseModel):
    """Podcast-specific metadata."""
    audio_url: Optional[HttpUrl] = None
    transcript: Optional[str] = None
    duration_seconds: Optional[int] = None
    episode_number: Optional[int] = None
    file_size_bytes: Optional[int] = None

class ContentData(BaseModel):
    """
    Unified content data model for passing between layers.
    """
    id: Optional[int] = None
    content_type: ContentType
    url: HttpUrl
    title: Optional[str] = None
    status: ContentStatus = ContentStatus.NEW
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Processing metadata
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Timestamps
    created_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    
    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, v, info):
        """Ensure metadata matches content type."""
        if info.data:
            content_type = info.data.get("content_type")
            if content_type == ContentType.ARTICLE:
                # Validate article metadata
                try:
                    ArticleMetadata(**v)
                except Exception as e:
                    raise ValueError(f"Invalid article metadata: {e}")
            elif content_type == ContentType.PODCAST:
                # Validate podcast metadata
                try:
                    PodcastMetadata(**v)
                except Exception as e:
                    raise ValueError(f"Invalid podcast metadata: {e}")
        return v
    
    def to_article_metadata(self) -> ArticleMetadata:
        """Convert metadata to ArticleMetadata."""
        if self.content_type != ContentType.ARTICLE:
            raise ValueError("Not an article")
        return ArticleMetadata(**self.metadata)
    
    def to_podcast_metadata(self) -> PodcastMetadata:
        """Convert metadata to PodcastMetadata."""
        if self.content_type != ContentType.PODCAST:
            raise ValueError("Not a podcast")
        return PodcastMetadata(**self.metadata)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }