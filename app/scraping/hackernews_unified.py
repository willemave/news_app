from typing import Any

import httpx

from app.core.logging import get_logger
from app.models.metadata import ContentType
from app.scraping.base import BaseScraper

logger = get_logger(__name__)


class HackerNewsUnifiedScraper(BaseScraper):
    """Unified scraper for Hacker News front page using the new architecture."""

    def __init__(self):
        super().__init__("HackerNews")
        self.base_url = "https://hacker-news.firebaseio.com/v0"
        self.hn_base_url = "https://news.ycombinator.com"

    def scrape(self) -> list[dict[str, Any]]:
        """Scrape HackerNews front page stories."""
        items = []

        with httpx.Client() as client:
            # Get top story IDs
            response = client.get(f"{self.base_url}/topstories.json")
            story_ids = response.json()[:10]  # Top 30 stories

            # Fetch each story
            for story_id in story_ids:
                try:
                    story_response = client.get(f"{self.base_url}/item/{story_id}.json")
                    story = story_response.json()

                    if not story or story.get("type") != "story":
                        continue

                    # Skip if no URL (Ask HN, etc)
                    if "url" not in story:
                        continue

                    item = {
                        "url": self._normalize_url(story["url"]),
                        "title": story.get("title"),
                        "content_type": ContentType.ARTICLE,
                        "metadata": {
                            "platform": "hackernews",  # Platform identifier
                            # Standardized format: platform:source
                            "source": "hackernews:HackerNews",
                            "hn_id": story_id,
                            "hn_url": f"{self.hn_base_url}/item?id={story_id}",
                            "score": story.get("score", 0),
                            "comments": story.get("descendants", 0),
                            "author": story.get("by"),
                        },
                    }

                    items.append(item)

                except Exception as e:
                    logger.error(f"Error fetching story {story_id}: {e}")
                    continue

        return items
