"""
Unified Substack scraper following the new architecture.
"""

import contextlib
import re
from datetime import datetime
from typing import Any

import feedparser
import yaml

from app.core.logging import get_logger
from app.models.metadata import ContentType
from app.scraping.base import BaseScraper
from app.utils.error_logger import create_error_logger

logger = get_logger(__name__)


def load_substack_feeds(config_path: str = "config/substack.yml") -> list[dict[str, Any]]:
    """Loads Substack feed URLs, names, and limits from a YAML file."""
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
        feeds = config.get("feeds", [])
        # Return list of dicts with url, name, and limit
        result = []
        for feed in feeds:
            if isinstance(feed, dict) and feed.get("url"):
                result.append(
                    {
                        "url": feed["url"],
                        "name": feed.get("name", "Unknown Substack"),
                        "limit": feed.get("limit", 10),  # Default limit of 10 if not specified
                    }
                )
            elif isinstance(feed, str):
                # Handle legacy format
                result.append(
                    {
                        "url": feed,
                        "name": "Unknown Substack",
                        "limit": 10,  # Default limit for legacy format
                    }
                )
        return result
    except FileNotFoundError:
        logger.error(f"Substack config file not found at: {config_path}")
        return []
    except Exception as e:
        logger.error(f"Error loading Substack config: {e}", exc_info=True)
        return []


class SubstackScraper(BaseScraper):
    """Scraper for Substack RSS feeds."""

    def __init__(self, config_path: str = "config/substack.yml"):
        super().__init__("Substack")
        self.feeds = load_substack_feeds(config_path)
        self.podcast_filter = re.compile(r"\b(podcast|transcript)\b", re.IGNORECASE)
        self.error_logger = create_error_logger("substack_scraper", "logs/errors")

    def scrape(self) -> list[dict[str, Any]]:
        """Scrape all configured Substack feeds with comprehensive error logging."""
        items = []

        if not self.feeds:
            logger.warning("No Substack feeds configured. Skipping scrape.")
            return items

        for feed_info in self.feeds:
            feed_url = feed_info.get("url")
            source_name = feed_info.get("name", "Unknown Substack")
            limit = feed_info.get("limit", 10)

            if not feed_url:
                logger.warning("Skipping empty feed URL.")
                continue

            logger.info(
                f"Scraping Substack feed: {feed_url} (source: {source_name}, limit: {limit})"
            )
            try:
                parsed_feed = feedparser.parse(feed_url)

                # Check for parsing issues
                if parsed_feed.bozo:
                    # Log detailed parsing error with new logger
                    self.error_logger.log_feed_error(
                        feed_url=feed_url,
                        error=parsed_feed.bozo_exception,
                        feed_name=parsed_feed.feed.get("title", "Unknown Feed"),
                        operation="feed_parsing",
                    )
                    # Only warn for serious parsing errors, not encoding issues
                    encoding_override = getattr(
                        feedparser.exceptions, "CharacterEncodingOverride", type(None)
                    )
                    if not isinstance(parsed_feed.bozo_exception, encoding_override):
                        logger.warning(
                            f"Feed {feed_url} may be ill-formed: {parsed_feed.bozo_exception}"
                        )
                    else:
                        logger.debug(
                            f"Feed {feed_url} has encoding declaration mismatch (not critical): "
                            f"{parsed_feed.bozo_exception}"
                        )

                # Extract feed name and description from the RSS feed
                feed_name = parsed_feed.feed.get("title", "Unknown Feed")
                feed_description = parsed_feed.feed.get("description", "")

                logger.info(f"Processing feed: {feed_name} - {feed_description}")

                # Apply limit to entries (similar to podcast scraper)
                entries_to_process = parsed_feed.entries[:limit]

                processed_entries = 0
                for entry in entries_to_process:
                    item = self._process_entry(
                        entry, feed_name, feed_description, feed_url, source_name
                    )
                    if item:
                        items.append(item)
                        processed_entries += 1

                logger.info(
                    f"Successfully processed {processed_entries} entries from {feed_name} "
                    f"(limit: {limit})"
                )

            except Exception as e:
                # Log comprehensive error details
                self.error_logger.log_feed_error(
                    feed_url=feed_url, error=e, feed_name="Unknown Feed", operation="feed_scraping"
                )
                logger.error(f"Error scraping feed {feed_url}: {e}", exc_info=True)

        logger.info(f"Substack scraping completed. Processed {len(items)} total items")
        return items

    def _process_entry(
        self,
        entry,
        feed_name: str,
        feed_description: str = "",
        feed_url: str = "",
        source_name: str = "",
    ) -> dict[str, Any]:
        """Process a single entry from an RSS feed."""
        title = entry.get("title", "No Title")
        link = entry.get("link")

        if not link:
            # Log detailed entry error
            self.error_logger.log_error(
                error=Exception(f"Missing link for entry: {title}"),
                operation="entry_processing",
                context={
                    "feed_url": feed_url,
                    "feed_name": feed_name,
                    "entry_title": title,
                    "entry_id": entry.get("id"),
                    "error_type": "missing_link",
                },
            )
            logger.warning(f"Skipping entry with no link in feed {feed_name}: {title}")
            return None

        # Filter out podcasts
        if self.podcast_filter.search(title):
            logger.info(f"Skipping podcast entry: {title}")
            return None

        # Extract content from RSS entry
        content = ""
        if "content" in entry and entry["content"]:
            for c in entry["content"]:
                if c.get("type") == "text/html":
                    content = c.get("value", "")
                    break
        if not content:
            content = entry.get("summary", "")

        # Parse publication date
        publication_date = None
        if entry.get("published_parsed"):
            with contextlib.suppress(TypeError, ValueError):
                publication_date = datetime(*entry["published_parsed"][:6])

        # Create item for unified system
        item = {
            "url": self._normalize_url(link),
            "title": title,
            "content_type": ContentType.ARTICLE,
            "metadata": {
                "platform": "substack",  # Platform identifier
                # Standardized format: platform:source
                "source": f"substack:{source_name or feed_name}",
                "feed_name": feed_name,
                "feed_description": feed_description,
                "author": entry.get("author"),
                "publication_date": publication_date.isoformat() if publication_date else None,
                "rss_content": content,  # Store RSS content for processing
                "word_count": len(content.split()) if content else 0,
                "entry_id": entry.get("id"),
                "tags": [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")],
            },
        }

        return item


def run_substack_scraper():
    """Initialize and run the Substack scraper."""
    scraper = SubstackScraper()
    return scraper.run()


if __name__ == "__main__":
    count = run_substack_scraper()
    print(f"Substack scraper processed {count} items")
