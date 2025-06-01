from sqlalchemy import Column, Integer, String, Text, DateTime, Enum
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
    
    # Summary fields (previously in Summaries table)
    short_summary = Column(Text, nullable=True)
    detailed_summary = Column(Text, nullable=True)
    summary_date = Column(DateTime, nullable=True)
    
    # Source field to track where the article came from
    source = Column(String, nullable=False, default="unknown", index=True)

class CronLogs(Base):
    __tablename__ = "cron_logs"

    id = Column(Integer, primary_key=True, index=True)
    run_date = Column(DateTime, default=datetime.utcnow)
    links_fetched = Column(Integer, default=0)
    successful_scrapes = Column(Integer, default=0)
    errors = Column(Text, nullable=True)
