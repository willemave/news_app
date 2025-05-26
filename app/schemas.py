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

class ArticleCreate(ArticleBase):
    pass

class Article(ArticleBase):
    id: int
    scraped_date: datetime
    status: str

    class Config:
        from_attributes = True
