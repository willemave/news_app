from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class LinkBase(BaseModel):
    url: HttpUrl
    source: str

class LinkCreate(LinkBase):
    pass

class Link(LinkBase):
    id: int
    status: str
    created_date: datetime
    processed_date: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True

class PodcastBase(BaseModel):
    title: str
    url: HttpUrl
    enclosure_url: HttpUrl
    podcast_feed_name: str
    publication_date: Optional[datetime]

class PodcastCreate(PodcastBase):
    pass

class PodcastResponse(PodcastBase):
    id: int
    file_path: Optional[str]
    transcribed_text_path: Optional[str]
    short_summary: Optional[str]
    detailed_summary: Optional[str]
    download_date: Optional[datetime]
    status: str
    created_date: datetime
    error_message: Optional[str]

    class Config:
        from_attributes = True

class PodcastListResponse(BaseModel):
    id: int
    title: str
    podcast_feed_name: str
    publication_date: Optional[datetime]
    status: str
    created_date: datetime
    short_summary: Optional[str]

    class Config:
        from_attributes = True

class ArticleSummary(BaseModel):
    """Pydantic model for LLM-generated article summaries."""
    short_summary: str
    detailed_summary: str

class ArticleBase(BaseModel):
    title: Optional[str]
    url: HttpUrl
    author: Optional[str]
    publication_date: Optional[datetime]

class ArticleCreate(ArticleBase):
    link_id: Optional[int] = None

class Article(ArticleBase):
    id: int
    scraped_date: datetime
    short_summary: Optional[str]
    detailed_summary: Optional[str]
    summary_date: Optional[datetime]
    link_id: Optional[int]

    class Config:
        from_attributes = True
