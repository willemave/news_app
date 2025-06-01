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
