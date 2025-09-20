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

                    # Derive source domain from the linked URL
                    try:
                        from urllib.parse import urlparse
                        host = urlparse(story["url"]).netloc or ""
                    except Exception:
                        host = ""

                    normalized_url = self._normalize_url(story["url"])
                    discussion_url = f"{self.hn_base_url}/item?id={story_id}"

                    item = {
                        "url": normalized_url,
                        "title": story.get("title"),
                        "content_type": ContentType.NEWS,
                        "is_aggregate": False,
                        "metadata": {
                            "platform": "hackernews",  # Scraper identifier
                            "source": host,
                            "items": [
                                {
                                    "title": story.get("title"),
                                    "url": normalized_url,
                                    "summary": story.get("text"),
                                    "source": host,
                                    "author": story.get("by"),
                                    "score": story.get("score", 0),
                                    "comments_url": discussion_url,
                                    "metadata": {
                                        "hn_id": story_id,
                                        "comments": story.get("descendants", 0),
                                        "score": story.get("score", 0),
                                    },
                                }
                            ],
                            "primary_url": discussion_url,
                            "excerpt": story.get("text"),
                        },
                    }

                    items.append(item)

                except Exception as e:
                    logger.error(f"Error fetching story {story_id}: {e}")
                    continue

        return items
