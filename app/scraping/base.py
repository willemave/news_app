from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.schema import Content
from app.models.metadata import ContentType, ContentStatus
from app.services.queue import get_queue_service, TaskType

logger = get_logger(__name__)

class BaseScraper(ABC):
    """Base class for all scrapers."""
    
    def __init__(self, name: str):
        self.name = name
        self.queue_service = get_queue_service()
    
    @abstractmethod
    async def scrape(self) -> List[Dict[str, Any]]:
        """
        Scrape content and return list of items.
        
        Each item should have:
        - url: str
        - title: Optional[str]
        - content_type: ContentType
        - metadata: Dict[str, Any]
        """
        pass
    
    async def run(self) -> int:
        """Run scraper and save results."""
        logger.info(f"Running {self.name} scraper")
        
        try:
            # Scrape items
            items = await self.scrape()
            logger.info(f"Scraped {len(items)} items from {self.name}")
            
            # Save to database
            saved_count = self._save_items(items)
            
            logger.info(f"Saved {saved_count} new items from {self.name}")
            return saved_count
            
        except Exception as e:
            logger.error(f"Error in {self.name} scraper: {e}")
            return 0
    
    def _save_items(self, items: List[Dict[str, Any]]) -> int:
        """Save scraped items to database."""
        saved_count = 0
        
        with get_db() as db:
            for item in items:
                try:
                    # Check if already exists
                    existing = db.query(Content).filter(
                        Content.url == item['url']
                    ).first()
                    
                    if existing:
                        logger.debug(f"URL already exists: {item['url']}")
                        continue
                    
                    # Create new content
                    content = Content(
                        content_type=item['content_type'].value,
                        url=item['url'],
                        title=item.get('title'),
                        status=ContentStatus.NEW.value,
                        content_metadata=item.get('metadata', {}),
                        created_at=datetime.utcnow()
                    )
                    
                    db.add(content)
                    db.commit()
                    db.refresh(content)
                    
                    # Queue for processing
                    self.queue_service.enqueue(
                        TaskType.PROCESS_CONTENT,
                        content_id=content.id
                    )
                    
                    saved_count += 1
                    
                except Exception as e:
                    db.rollback()
                    if "UNIQUE constraint failed" in str(e) or "duplicate key value" in str(e):
                        logger.debug(f"URL already exists (race condition): {item['url']}")
                    else:
                        logger.error(f"Error saving item {item['url']}: {e}")
                    continue
        
        return saved_count
    
    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistency."""
        # Remove trailing slashes
        url = url.rstrip('/')
        
        # Ensure https
        if url.startswith('http://'):
            url = url.replace('http://', 'https://', 1)
        
        return url