"""Unified Atom feed scraper following the new architecture."""

import contextlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import feedparser
import yaml

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.metadata import ContentType
from app.scraping.base import BaseScraper
from app.utils.error_logger import create_error_logger, log_scraper_event
from app.utils.paths import resolve_config_directory, resolve_config_path
from app.services.scraper_configs import build_feed_payloads, list_active_configs_by_type

ENCODING_OVERRIDE_EXCEPTIONS = tuple(
    exc
    for exc in (
        getattr(feedparser, "CharacterEncodingOverride", None),
        getattr(getattr(feedparser, "exceptions", None), "CharacterEncodingOverride", None),
    )
    if isinstance(exc, type)
)

logger = get_logger(__name__)
_MISSING_CONFIG_WARNINGS: set[str] = set()


def _resolve_atom_config_path(config_path: str | Path | None) -> Path:
    """Resolve the Atom config path."""
    if config_path is None:
        return resolve_config_path("ATOM_CONFIG_PATH", "atom.yml")

    candidate = Path(config_path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve(strict=False)

    base_dir = resolve_config_directory()
    return (base_dir / candidate).resolve(strict=False)


def _emit_missing_config_warning(resolved_path: Path) -> None:
    """Emit a warning for missing config file (only once)."""
    key = str(resolved_path.resolve(strict=False))
    if key in _MISSING_CONFIG_WARNINGS:
        return
    _MISSING_CONFIG_WARNINGS.add(key)
    log_scraper_event(
        service="Atom",
        event="config_missing",
        level=logging.WARNING,
        metric="scrape_config_missing",
        path=str(resolved_path.resolve(strict=False)),
    )


def load_atom_feeds(config_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Loads Atom feed URLs, names, and limits from a YAML file."""
    resolved_path = _resolve_atom_config_path(config_path)

    if not resolved_path.exists():
        _emit_missing_config_warning(resolved_path)
        return []

    try:
        with open(resolved_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
    except Exception as exc:
        log_scraper_event(
            service="Atom",
            event="config_load_failed",
            level=logging.ERROR,
            path=str(resolved_path),
            error=str(exc),
        )
        return []

    feeds = config.get("feeds", [])
    result: list[dict[str, Any]] = []
    for feed in feeds:
        if isinstance(feed, dict) and feed.get("url"):
            result.append(
                {
                    "url": feed["url"],
                    "name": feed.get("name", "Unknown Atom"),
                    "limit": feed.get("limit", 10),
                }
            )
        elif isinstance(feed, str):
            result.append(
                {
                    "url": feed,
                    "name": "Unknown Atom",
                    "limit": 10,
                }
            )
    return result


class AtomScraper(BaseScraper):
    """Scraper for Atom feeds."""

    def __init__(self, config_path: str | Path | None = None):
        super().__init__("Atom")
        self.error_logger = create_error_logger("atom_scraper", "logs/errors")

    def _load_feeds(self) -> list[dict[str, Any]]:
        """Load active Atom feeds for all users."""
        with get_db() as db:
            configs = list_active_configs_by_type(db, "atom")
            return build_feed_payloads(configs)

    def scrape(self) -> list[dict[str, Any]]:
        """Scrape all configured Atom feeds with comprehensive error logging."""
        items = []

        feeds = self._load_feeds()
        if not feeds:
            logger.warning("No Atom feeds configured. Skipping scrape.")
            return items

        for feed_info in feeds:
            feed_url = feed_info.get("url")
            source_name = feed_info.get("name", "Unknown Atom")
            limit = feed_info.get("limit", 10)
            user_id = feed_info.get("user_id")

            if not feed_url:
                logger.warning("Skipping empty feed URL.")
                continue

            logger.info(f"Scraping Atom feed: {feed_url} (source: {source_name}, limit: {limit})")
            try:
                parsed_feed = feedparser.parse(feed_url)

                logger.debug(
                    "Parsed feed %s (entries=%s, bozo=%s, feed_title=%s)",
                    feed_url,
                    len(getattr(parsed_feed, "entries", []) or []),
                    getattr(parsed_feed, "bozo", False),
                    parsed_feed.feed.get("title") if parsed_feed.feed else "<no-title>",
                )

                # Check for parsing issues
                if parsed_feed.bozo:
                    bozo_exc = parsed_feed.bozo_exception

                    if ENCODING_OVERRIDE_EXCEPTIONS and isinstance(
                        bozo_exc, ENCODING_OVERRIDE_EXCEPTIONS
                    ):
                        logger.debug(
                            (
                                "Feed %s has encoding declaration mismatch "
                                "(CharacterEncodingOverride): %s"
                            ),
                            feed_url,
                            bozo_exc,
                        )
                    else:
                        # Log detailed parsing error
                        self.error_logger.log_feed_error(
                            feed_url=feed_url,
                            error=bozo_exc,
                            feed_name=parsed_feed.feed.get("title", "Unknown Feed"),
                            operation="feed_parsing",
                        )
                        logger.warning("Feed %s may be ill-formed: %s", feed_url, bozo_exc)

                # Extract feed name and description
                feed_name = parsed_feed.feed.get("title", "Unknown Feed")
                feed_description = parsed_feed.feed.get("subtitle", "") or parsed_feed.feed.get(
                    "description", ""
                )

                logger.info(f"Processing feed: {feed_name} - {feed_description}")

                # Apply limit to entries
                entries_to_process = parsed_feed.entries[:limit]

                processed_entries = 0
                for entry in entries_to_process:
                    item = self._process_entry(
                        entry, feed_name, feed_description, feed_url, source_name, user_id
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

        logger.info(f"Atom scraping completed. Processed {len(items)} total items")
        return items

    def _process_entry(
        self,
        entry,
        feed_name: str,
        feed_description: str = "",
        feed_url: str = "",
        source_name: str = "",
        user_id: int | None = None,
    ) -> dict[str, Any] | None:
        """Process a single entry from an Atom feed."""
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

        # Extract content from Atom entry
        content = ""
        if "content" in entry and entry["content"]:
            for c in entry["content"]:
                if c.get("type") in ("text/html", "html"):
                    content = c.get("value", "")
                    break
        if not content:
            content = entry.get("summary", "")

        logger.debug(
            "Entry debug: feed=%s title=%s content_chars=%s summary_chars=%s link=%s",
            feed_name,
            title,
            len(content or ""),
            len(entry.get("summary", "") or ""),
            link,
        )

        # Parse publication date (Atom uses 'updated' or 'published')
        publication_date = None
        date_field = entry.get("published_parsed") or entry.get("updated_parsed")
        if date_field:
            with contextlib.suppress(TypeError, ValueError):
                publication_date = datetime(*date_field[:6])

        # Determine domain for metadata
        try:
            from urllib.parse import urlparse

            host = urlparse(link).netloc or ""
        except Exception:
            host = ""

        item = {
            "url": self._normalize_url(link),
            "title": title,
            "content_type": ContentType.ARTICLE,
            "user_id": user_id,
            "metadata": {
                "platform": "atom",  # Scraper identifier
                "source": source_name,  # Configured name from YAML
                "source_domain": host,
                "feed_name": feed_name,
                "feed_description": feed_description,
                "author": entry.get("author"),
                "publication_date": publication_date.isoformat() if publication_date else None,
                "rss_content": content,  # Store content for processing
                "word_count": len(content.split()) if content else 0,
                "entry_id": entry.get("id"),
                "tags": [tag.get("term") for tag in entry.get("tags", []) if tag.get("term")],
            },
        }

        logger.debug(
            "Emitted Atom item: url=%s word_count=%s publication_date=%s tags=%s",
            item["url"],
            item["metadata"].get("word_count"),
            item["metadata"].get("publication_date"),
            item["metadata"].get("tags"),
        )

        return item


def run_atom_scraper():
    """Initialize and run the Atom scraper."""
    scraper = AtomScraper()
    return scraper.run()


if __name__ == "__main__":
    count = run_atom_scraper()
    print(f"Atom scraper processed {count} items")
