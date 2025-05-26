from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .database import Base

class ArticleStatus(enum.Enum):
    new = "new"
    scraped = "scraped"
    failed = "failed"
    processed = "processed"
    approved = "approved"

class Articles(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    url = Column(String, unique=True, index=True, nullable=False)
    author = Column(String, nullable=True)
    publication_date = Column(DateTime, nullable=True)
    raw_content = Column(Text, nullable=True)
    scraped_date = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(ArticleStatus), default=ArticleStatus.new)

class Summaries(Base):
    __tablename__ = "summaries"

    id = Column(Integer, primary_key=True, index=True)
    article_id = Column(Integer, ForeignKey("articles.id"))
    short_summary = Column(Text, nullable=True)
    detailed_summary = Column(Text, nullable=True)
    summary_date = Column(DateTime, default=datetime.utcnow)

    # Relationship
    article = relationship("Articles", back_populates="summaries")

Articles.summaries = relationship("Summaries", back_populates="article")

class CronLogs(Base):
    __tablename__ = "cron_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_date = Column(DateTime, default=datetime.utcnow)
    links_fetched = Column(Integer, default=0)
    successful_scrapes = Column(Integer, default=0)
    errors = Column(Text, nullable=True)
