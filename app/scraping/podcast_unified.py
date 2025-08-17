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


class PodcastUnifiedScraper(BaseScraper):
    """Unified podcast RSS scraper following new architecture."""

    def __init__(self, config_path: str = "config/podcasts.yml"):
        super().__init__("Podcast")
        self.config_path = config_path
        self.feeds = self._load_podcast_feeds()
        self.error_logger = create_error_logger("podcast_scraper", "logs/errors")

    def _load_podcast_feeds(self) -> list[dict]:
        """Load podcast feed URLs from YAML config."""
        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            feeds = config.get("feeds", [])
            logger.info(f"Loaded {len(feeds)} podcast feeds from config")
            return feeds
        except FileNotFoundError:
            logger.error(f"Podcast config file not found at: {self.config_path}")
            return []
        except Exception as e:
            logger.error(f"Error loading podcast config: {e}")
            return []

    def scrape(self) -> list[dict[str, Any]]:
        """Scrape all configured podcast feeds with comprehensive error logging."""
        if not self.feeds:
            logger.warning("No podcast feeds configured")
            return []

        items = []

        for feed_config in self.feeds:
            if not isinstance(feed_config, dict):
                logger.warning("Invalid feed configuration, skipping")
                continue

            feed_name = feed_config.get("name", "Unknown Feed")
            feed_url = feed_config.get("url")
            limit = feed_config.get("limit", 10)

            if not feed_url:
                logger.warning(f"No URL found for feed: {feed_name}")
                continue

            logger.info(f"Scraping podcast feed: {feed_name} (limit: {limit})")

            try:
                # Parse RSS feed with better encoding handling
                parsed_feed = feedparser.parse(feed_url)

                # Check for parsing issues
                if parsed_feed.bozo:
                    exception_str = str(parsed_feed.bozo_exception).lower()
                    
                    # Check for critical errors that should skip processing
                    is_critical_error = False
                    
                    # Check if it's HTML instead of XML
                    if "is not an xml media type" in exception_str:
                        logger.error(f"Feed {feed_url} returned HTML instead of XML. Skipping.")
                        self.error_logger.log_feed_error(
                            feed_url=feed_url,
                            error=parsed_feed.bozo_exception,
                            feed_name=feed_name,
                            operation="feed_parsing",
                        )
                        continue
                    
                    # Check for malformed XML
                    if "not well-formed" in exception_str or "saxparseexception" in exception_str:
                        logger.error(f"Feed {feed_url} contains malformed XML. Skipping.")
                        self.error_logger.log_feed_error(
                            feed_url=feed_url,
                            error=parsed_feed.bozo_exception,
                            feed_name=feed_name,
                            operation="feed_parsing",
                        )
                        continue
                    
                    # Check if it's just an encoding mismatch (not critical)
                    is_encoding_issue = False
                    if "encoding" in exception_str or "declared as" in exception_str:
                        is_encoding_issue = True

                    # Only log other errors
                    if not is_encoding_issue:
                        self.error_logger.log_feed_error(
                            feed_url=feed_url,
                            error=parsed_feed.bozo_exception,
                            feed_name=feed_name,
                            operation="feed_parsing",
                        )
                        logger.warning(
                            f"Feed {feed_url} may be ill-formed: {parsed_feed.bozo_exception}"
                        )
                    else:
                        logger.debug(
                            f"Feed {feed_url} has encoding declaration mismatch "
                            f"(not critical): {parsed_feed.bozo_exception}"
                        )

                feed_info = getattr(parsed_feed, "feed", {})
                logger.debug(f"Feed title: {feed_info.get('title', 'N/A')}")
                logger.debug(f"Total entries: {len(parsed_feed.entries)}")
                
                # Check if feed has entries
                if not parsed_feed.entries:
                    logger.warning(f"Feed {feed_url} has no entries. Skipping.")
                    continue

                # Process entries (limited)
                entries_to_process = parsed_feed.entries[:limit]
                logger.info(f"Processing {len(entries_to_process)} episodes from {feed_name}")

                processed_entries = 0
                for entry in entries_to_process:
                    item = self._process_entry(entry, feed_name, feed_info, feed_url)
                    if item:
                        items.append(item)
                        processed_entries += 1

                logger.info(f"Successfully processed {processed_entries} episodes from {feed_name}")

            except Exception as e:
                # Log comprehensive error details
                self.error_logger.log_feed_error(
                    feed_url=feed_url, error=e, feed_name=feed_name, operation="feed_scraping"
                )
                logger.error(f"Error scraping feed {feed_url}: {e}")

        logger.info(f"Podcast scraping completed. Processed {len(items)} total items")
        return items

    def _process_entry(
        self, entry, feed_name: str, feed_info: dict, feed_url: str
    ) -> dict[str, Any]:
        """Process a single podcast entry."""
        title = entry.get("title", "No Title")
        link = entry.get("link")

        # Find audio enclosure URL first (this is the most important for podcasts)
        enclosure_url = self._find_audio_enclosure(entry, title)
        if not enclosure_url:
            logger.warning(f"No audio enclosure found for: {title}")
            return None

        # If no link but we have audio, create a fallback link using entry ID or audio URL
        if not link:
            # Try to use entry ID as fallback, but only if it looks like a URL
            entry_id = entry.get("id")
            entry_guid = entry.get("guid")

            if entry_id and (entry_id.startswith("http") or entry_id.startswith("https")):
                link = entry_id
            elif entry_guid and (entry_guid.startswith("http") or entry_guid.startswith("https")):
                link = entry_guid
            else:
                # Use the audio URL as fallback (this ensures we don't lose the episode)
                link = enclosure_url

            logger.info(f"Using fallback link for '{title}': {link}")

        # Extract publication date
        publication_date = None
        if entry.get("published_parsed"):
            try:
                publication_date = datetime(*entry.published_parsed[:6])
            except Exception as e:
                logger.debug(f"Error parsing publication date: {e}")

        # Extract episode number if available
        episode_number = None
        episode_str = entry.get("itunes_episode") or entry.get("episode")
        if episode_str:
            with contextlib.suppress(ValueError, TypeError):
                episode_number = int(episode_str)

        # Extract duration if available
        duration = None
        duration_str = entry.get("itunes_duration")
        if duration_str:
            duration = self._parse_duration(duration_str)

        # Build metadata
        metadata = {
            "platform": "podcast",  # Platform identifier
            "source": f"podcast:{feed_name}",  # Standardized format: platform:source
            "audio_url": enclosure_url,
            "publication_date": publication_date.isoformat() if publication_date else None,
            "episode_number": episode_number,
            "duration_seconds": duration,
            "feed_name": feed_name,
            "feed_title": feed_info.get("title"),
            "feed_description": feed_info.get("description"),
            "author": entry.get("author") or feed_info.get("author"),
            "description": entry.get("description") or entry.get("summary"),
        }

        return {
            "url": self._normalize_url(link),
            "title": title,
            "content_type": ContentType.PODCAST,
            "metadata": metadata,
        }

    def _find_audio_enclosure(self, entry, title: str) -> str:
        """Find the audio enclosure URL for a podcast entry."""
        # Check enclosures first
        if hasattr(entry, "enclosures") and entry.enclosures:
            for enclosure in entry.enclosures:
                if enclosure.type and "audio" in enclosure.type:
                    logger.debug(f"Found audio enclosure for '{title}': {enclosure.href}")
                    return enclosure.href

        # Fallback: check links for audio content
        for link_item in getattr(entry, "links", []):
            link_href = link_item.get("href", "")
            link_type = link_item.get("type", "")

            # Check by MIME type
            if link_type and "audio" in link_type:
                logger.debug(f"Found audio link by type for '{title}': {link_href}")
                return link_href

            # Check by file extension
            if link_href and any(
                ext in link_href.lower() for ext in [".mp3", ".m4a", ".wav", ".ogg"]
            ):
                logger.debug(f"Found audio link by extension for '{title}': {link_href}")
                return link_href

        return None

    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds."""
        try:
            # Handle formats like "1:23:45" or "23:45" or "123"
            parts = duration_str.split(":")
            if len(parts) == 3:  # H:M:S
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            elif len(parts) == 2:  # M:S
                minutes, seconds = map(int, parts)
                return minutes * 60 + seconds
            else:  # Just seconds
                return int(duration_str)
        except (ValueError, TypeError):
            logger.debug(f"Could not parse duration: {duration_str}")
            return None

    def _sanitize_filename(self, title: str) -> str:
        """Sanitize title for filename use."""
        # Remove invalid characters
        sanitized = re.sub(r"[^\w\s-]", "", title).strip()
        # Replace spaces with hyphens
        sanitized = re.sub(r"[-\s]+", "-", sanitized)
        # Truncate to reasonable length
        return sanitized[:100]
