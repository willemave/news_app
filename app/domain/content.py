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
    
    @property
    def summary(self) -> Optional[str]:
        """Get summary text (either simple or overview from structured)."""
        summary_data = self.metadata.get('summary')
        if not summary_data:
            return None
        if isinstance(summary_data, str):
            return summary_data
        if isinstance(summary_data, dict):
            return summary_data.get('overview', '')
        return None
    
    @property
    def short_summary(self) -> Optional[str]:
        """Get short version of summary for list view."""
        summary = self.summary
        if not summary:
            return None
        # Return first 200 chars
        if len(summary) > 200:
            return summary[:197] + "..."
        return summary
    
    @property
    def structured_summary(self) -> Optional[Dict[str, Any]]:
        """Get structured summary if available."""
        summary_data = self.metadata.get('summary')
        if isinstance(summary_data, dict) and 'bullet_points' in summary_data:
            return summary_data
        return None
    
    @property
    def bullet_points(self) -> List[Dict[str, str]]:
        """Get bullet points from structured summary."""
        if self.structured_summary:
            return self.structured_summary.get('bullet_points', [])
        return []
    
    @property
    def quotes(self) -> List[Dict[str, str]]:
        """Get quotes from structured summary."""
        if self.structured_summary:
            return self.structured_summary.get('quotes', [])
        return []
    
    @property
    def topics(self) -> List[str]:
        """Get topics from structured summary."""
        if self.structured_summary:
            return self.structured_summary.get('topics', [])
        return self.metadata.get('topics', [])
    
    @property
    def transcript(self) -> Optional[str]:
        """Get transcript for podcasts."""
        if self.content_type == ContentType.PODCAST:
            return self.metadata.get('transcript')
        return None