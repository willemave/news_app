from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from .database import Base

class LinkStatus(enum.Enum):
    new = "new"
    processing = "processing"
    processed = "processed"
    failed = "failed"

class ArticleStatus(enum.Enum):
    new = "new"
    scraped = "scraped"
    failed = "failed"
    processed = "processed"
    approved = "approved"

class FailurePhase(enum.Enum):
    scraper = "scraper"
    processor = "processor"

class Links(Base):
    __tablename__ = "links"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    source = Column(String, nullable=False, index=True)  # "hackernews", "reddit-front", etc.
    status = Column(Enum(LinkStatus), default=LinkStatus.new, index=True)
    created_date = Column(DateTime, default=datetime.utcnow)
    processed_date = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relationship to Article
    article = relationship("Articles", back_populates="link", uselist=False)

class Articles(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=True)
    url = Column(String, unique=True, index=True, nullable=False)
    author = Column(String, nullable=True)
    publication_date = Column(DateTime, nullable=True)
    scraped_date = Column(DateTime, default=datetime.utcnow)
    
    # Summary fields (previously in Summaries table)
    short_summary = Column(Text, nullable=True)
    detailed_summary = Column(Text, nullable=True)
    summary_date = Column(DateTime, nullable=True)
    
    # Link to the source link record
    link_id = Column(Integer, ForeignKey("links.id"), nullable=True, index=True)
    link = relationship("Links", back_populates="article")

class FailureLogs(Base):
    __tablename__ = "failure_logs"

    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("links.id"), nullable=True, index=True)
    phase = Column(Enum(FailurePhase), nullable=False, index=True)
    error_msg = Column(Text, nullable=False)
    created_date = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationship to Link
    link = relationship("Links", foreign_keys=[link_id])

class CronLogs(Base):
    __tablename__ = "cron_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_date = Column(DateTime, default=datetime.utcnow)
    links_fetched = Column(Integer, default=0)
    successful_scrapes = Column(Integer, default=0)
    errors = Column(Text, nullable=True)
