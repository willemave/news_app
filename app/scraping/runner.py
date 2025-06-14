import asyncio
from typing import List, Optional, Dict

from app.scraping.base import BaseScraper
from app.scraping.hackernews_unified import HackerNewsUnifiedScraper
from app.scraping.reddit_unified import RedditUnifiedScraper
from app.scraping.substack_unified import SubstackScraper
from app.scraping.podcast_unified import PodcastUnifiedScraper
from app.core.logging import get_logger

logger = get_logger(__name__)

class ScraperRunner:
    """Manages and runs all scrapers."""
    
    def __init__(self):
        self.scrapers: List[BaseScraper] = [
            HackerNewsUnifiedScraper(),
            RedditUnifiedScraper(),
            SubstackScraper(),
            PodcastUnifiedScraper(),
        ]
    
    async def run_all(self) -> Dict[str, int]:
        """Run all scrapers and return results."""
        logger.info("Starting all scrapers")
        
        results = {}
        tasks = []
        
        for scraper in self.scrapers:
            task = asyncio.create_task(scraper.run())
            tasks.append((scraper.name, task))
        
        # Wait for all scrapers to complete
        for name, task in tasks:
            try:
                count = await task
                results[name] = count
            except Exception as e:
                logger.error(f"Scraper {name} failed: {e}")
                results[name] = 0
        
        total = sum(results.values())
        logger.info(f"All scrapers complete. Total items: {total}")
        
        return results
    
    async def run_scraper(self, name: str) -> Optional[int]:
        """Run a specific scraper by name."""
        for scraper in self.scrapers:
            if scraper.name.lower() == name.lower():
                return await scraper.run()
        
        logger.error(f"Scraper not found: {name}")
        return None
    
    def list_scrapers(self) -> List[str]:
        """List all available scrapers."""
        return [scraper.name for scraper in self.scrapers]