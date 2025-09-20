from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.metadata import ContentStatus
from app.models.schema import Content
from app.models.scraper_runs import ScraperStats
from app.services.queue import TaskType, get_queue_service

logger = get_logger(__name__)

"""
Source and Platform Conventions (updated):
-----------------------------------------
All scrapers must set both 'platform' and 'source' fields in metadata:

1) platform: the scraper identifier (lowercase), e.g.
   - hackernews, reddit, substack, podcast, twitter, youtube

2) source: the full domain name of the linked content, except for Reddit
   - For Reddit only, source is the subreddit name (e.g., MachineLearning)
   - Examples:
     - Hacker News link to https://github.com/... → platform=hackernews, source=github.com
     - Substack link https://importai.substack.com/... → platform=substack, source=importai.substack.com
     - Reddit post in r/MachineLearning → platform=reddit, source=MachineLearning
     - Podcast episode page https://stratechery.com/... → platform=podcast, source=stratechery.com

This convention keeps platform stable for filtering (by scraper) and source useful for grouping by site.
"""


class BaseScraper(ABC):
    """Base class for all scrapers."""

    def __init__(self, name: str):
        self.name = name
        self.queue_service = get_queue_service()

    @abstractmethod
    def scrape(self) -> list[dict[str, Any]]:
        """
        Scrape content and return list of items.

        Each item should have:
        - url: str
        - title: Optional[str]
        - content_type: ContentType
        - metadata: Dict[str, Any]
        """
        pass

    def run(self) -> int:
        """Run scraper and save results. Returns saved count for backward compatibility."""
        stats = self.run_with_stats()
        return stats.saved

    def run_with_stats(self) -> ScraperStats:
        """Run scraper and return detailed statistics."""
        logger.info(f"Running {self.name} scraper")

        stats = ScraperStats()

        try:
            # Scrape items
            items = self.scrape()
            stats.scraped = len(items)
            logger.info(f"Scraped {stats.scraped} items from {self.name}")

            # Save to database
            save_stats = self._save_items_with_stats(items)
            stats.saved = save_stats["saved"]
            stats.duplicates = save_stats["duplicates"]
            stats.errors = save_stats["errors"]
            stats.error_details = save_stats["error_details"]

            logger.info(
                f"Saved {stats.saved} new items from {self.name} "
                f"(duplicates: {stats.duplicates}, errors: {stats.errors})"
            )

        except Exception as e:
            logger.error(f"Error in {self.name} scraper: {e}")
            stats.errors = 1
            stats.error_details = [str(e)]

        return stats

    def _save_items(self, items: list[dict[str, Any]]) -> int:
        """Save scraped items to database. Returns saved count for backward compatibility."""
        stats = self._save_items_with_stats(items)
        return stats["saved"]

    def _save_items_with_stats(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Save scraped items to database and return detailed statistics."""
        saved_count = 0
        duplicate_count = 0
        error_count = 0
        error_details = []

        with get_db() as db:
            for item in items:
                try:
                    # Check if already exists
                    existing = db.query(Content).filter(Content.url == item["url"]).first()

                    if existing:
                        logger.debug(f"URL already exists: {item['url']}")
                        duplicate_count += 1
                        continue

                    # Create new content
                    metadata = item.get("metadata", {})
                    content = Content(
                        content_type=item["content_type"].value,
                        url=item["url"],
                        title=item.get("title"),
                        source=metadata.get("source"),  # Extract source from metadata
                        platform=metadata.get("platform"),  # Extract platform from metadata
                        is_aggregate=bool(item.get("is_aggregate", False)),
                        status=ContentStatus.NEW.value,
                        content_metadata=metadata,
                        created_at=datetime.utcnow(),
                    )

                    db.add(content)
                    db.commit()
                    db.refresh(content)

                    # Queue for processing
                    self.queue_service.enqueue(TaskType.PROCESS_CONTENT, content_id=content.id)

                    saved_count += 1

                except Exception as e:
                    db.rollback()
                    if "UNIQUE constraint failed" in str(e) or "duplicate key value" in str(e):
                        logger.debug(f"URL already exists (race condition): {item['url']}")
                        duplicate_count += 1
                    else:
                        logger.error(f"Error saving item {item['url']}: {e}")
                        error_count += 1
                        error_details.append(f"Error saving {item.get('url', 'unknown')}: {str(e)}")
                    continue

        return {
            "saved": saved_count,
            "duplicates": duplicate_count,
            "errors": error_count,
            "error_details": error_details,
        }

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for consistency."""
        # Remove trailing slashes
        url = url.rstrip("/")

        # Ensure https
        if url.startswith("http://"):
            url = url.replace("http://", "https://", 1)

        return url
