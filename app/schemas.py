from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class LinkCreate(BaseModel):
    url: HttpUrl

class ArticleBase(BaseModel):
    title: Optional[str]
    url: HttpUrl
    author: Optional[str]
    publication_date: Optional[datetime]
    source: Optional[str] = "unknown"

class ArticleCreate(ArticleBase):
    raw_content: Optional[str] = None

class Article(ArticleBase):
    id: int
    raw_content: Optional[str]
    scraped_date: datetime
    status: str
    short_summary: Optional[str]
    detailed_summary: Optional[str]
    summary_date: Optional[datetime]

    class Config:
        from_attributes = True
