import feedparser
import yaml
import re
import os
from typing import List
from datetime import datetime
from app.database import SessionLocal
from app.models import Podcasts
from app.config import logger

def sanitize_filename(title: str) -> str:
    """Sanitizes a title to be a valid filename."""
    # Remove invalid characters
    sanitized = re.sub(r'[^\w\s-]', '', title).strip()
    # Replace spaces with hyphens
    sanitized = re.sub(r'[-\s]+', '-', sanitized)
    # Truncate to a reasonable length
    return sanitized[:100]

def load_podcast_feeds(config_path: str = 'config/podcasts.yml') -> List[dict]:
    """Loads podcast feed URLs from a YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        feeds = config.get('feeds', [])
        return feeds
    except FileNotFoundError:
        logger.error(f"Podcast config file not found at: {config_path}")
        return []
    except Exception as e:
        logger.error(f"Error loading podcast config: {e}", exc_info=True)
        return []

class PodcastRSSScraper:
    def __init__(self, config_path: str = 'config/podcasts.yml', debug: bool = False):
        self.feeds = load_podcast_feeds(config_path)
        self.debug = debug
        
        # Set debug logging if requested
        if self.debug:
            logger.setLevel(10)  # DEBUG level
            logger.info("Debug logging enabled for podcast scraper")

    def scrape(self):
        """Scrapes all configured podcast feeds."""
        if not self.feeds:
            logger.warning("No podcast feeds configured. Skipping scrape.")
            return

        for feed_config in self.feeds:
            if not isinstance(feed_config, dict):
                logger.warning("Invalid feed configuration, skipping.")
                continue
                
            feed_name = feed_config.get('name', 'Unknown Feed')
            feed_url = feed_config.get('url')
            limit = feed_config.get('limit', 10)  # Default to 10 if not specified
            
            if not feed_url:
                logger.warning(f"No URL found for feed: {feed_name}")
                continue

            logger.info(f"Scraping podcast feed: {feed_name} - {feed_url} (limit: {limit})")
            try:
                parsed_feed = feedparser.parse(feed_url)
                
                # Log feed parsing results
                logger.debug(f"Feed parsing status - bozo: {parsed_feed.bozo}")
                if parsed_feed.bozo:
                    logger.warning(f"Feed {feed_url} may be ill-formed: {parsed_feed.bozo_exception}")
                
                # Log feed metadata
                feed_info = getattr(parsed_feed, 'feed', {})
                logger.debug(f"Feed title: {feed_info.get('title', 'N/A')}")
                logger.debug(f"Feed description: {feed_info.get('description', 'N/A')[:100]}...")
                logger.debug(f"Total entries in feed: {len(parsed_feed.entries)}")
                
                logger.info(f"Processing feed: {feed_name}")
                
                # Limit the number of entries processed
                entries_to_process = parsed_feed.entries[:limit]
                logger.info(f"Processing {len(entries_to_process)} most recent episodes (limit: {limit})")
                
                if len(entries_to_process) == 0:
                    logger.warning(f"No entries found in feed {feed_name} ({feed_url})")
                
                for entry in entries_to_process:
                    self.process_entry(entry, feed_name)

            except Exception as e:
                logger.error(f"Error scraping feed {feed_url}: {e}", exc_info=True)

    def process_entry(self, entry, feed_name: str):
        """Processes a single entry from a podcast RSS feed."""
        title = entry.get('title', 'No Title')
        link = entry.get('link')

        # Debug logging for entry structure
        logger.debug(f"Processing entry '{title}' from feed '{feed_name}'")
        logger.debug(f"Entry keys available: {list(entry.keys())}")
        logger.debug(f"Entry link field: {link}")
        
        # Log all available links in the entry for debugging
        if hasattr(entry, 'links'):
            logger.debug(f"Entry.links found: {len(entry.links)} links")
            for i, link_item in enumerate(entry.links):
                logger.debug(f"  Link {i}: href='{link_item.get('href')}', type='{link_item.get('type')}', rel='{link_item.get('rel')}'")
        else:
            logger.debug("No entry.links attribute found")

        if not link:
            logger.warning(f"Skipping entry with no link in feed {feed_name}: {title}")
            logger.warning(f"Available entry fields: {list(entry.keys())}")
            # Try to find alternative link fields
            alt_link = None
            if hasattr(entry, 'links') and entry.links:
                for link_item in entry.links:
                    if link_item.get('rel') == 'alternate' and link_item.get('href'):
                        alt_link = link_item.get('href')
                        logger.info(f"Found alternate link for '{title}': {alt_link}")
                        break
            if not alt_link:
                logger.warning(f"No alternate links found for entry '{title}' in feed '{feed_name}'")
            return

        # Find the audio enclosure URL
        enclosure_url = None
        logger.debug(f"Looking for audio enclosure for '{title}'")
        
        # Check enclosures first
        if hasattr(entry, 'enclosures') and entry.enclosures:
            logger.debug(f"Found {len(entry.enclosures)} enclosures")
            for i, enclosure in enumerate(entry.enclosures):
                logger.debug(f"  Enclosure {i}: href='{enclosure.href}', type='{enclosure.type}', length='{getattr(enclosure, 'length', 'N/A')}'")
                if enclosure.type and 'audio' in enclosure.type:
                    enclosure_url = enclosure.href
                    logger.info(f"Found audio enclosure for '{title}': {enclosure_url} (type: {enclosure.type})")
                    break
        else:
            logger.debug("No enclosures attribute found or enclosures list is empty")
        
        # Fallback: look for links with audio extensions
        if not enclosure_url:
            logger.debug("No audio enclosure found, checking links for audio files")
            links_checked = 0
            for link_item in getattr(entry, 'links', []):
                links_checked += 1
                link_href = link_item.get('href', '')
                link_type = link_item.get('type', '')
                logger.debug(f"  Checking link {links_checked}: href='{link_href}', type='{link_type}'")
                
                if link_type and 'audio' in link_type:
                    enclosure_url = link_href
                    logger.info(f"Found audio link by type for '{title}': {enclosure_url} (type: {link_type})")
                    break
                elif link_href and any(ext in link_href for ext in ['.mp3', '.m4a', '.wav']):
                    enclosure_url = link_href
                    logger.info(f"Found audio link by extension for '{title}': {enclosure_url}")
                    break
            
            if links_checked == 0:
                logger.debug("No links found to check for audio files")

        if not enclosure_url:
            logger.warning(f"No audio enclosure found for podcast: {title}")
            logger.warning(f"Entry had {len(getattr(entry, 'enclosures', []))} enclosures and {len(getattr(entry, 'links', []))} links")
            return

        # Create podcast record
        self.create_podcast_record(entry, feed_name, enclosure_url)

    def create_podcast_record(self, entry, feed_name: str, enclosure_url: str):
        """Creates a podcast record in the database."""
        title = entry.get('title', 'No Title')
        link_url = entry.get('link')
        
        logger.debug(f"Creating podcast record for '{title}'")
        logger.debug(f"  URL: {link_url}")
        logger.debug(f"  Enclosure URL: {enclosure_url}")
        logger.debug(f"  Feed: {feed_name}")
        
        db = SessionLocal()
        try:
            # Check if podcast already exists
            existing_podcast = db.query(Podcasts).filter(Podcasts.url == link_url).first()
            if existing_podcast:
                logger.info(f"Podcast already exists, skipping: {title}")
                logger.debug(f"  Existing podcast ID: {existing_podcast.id}, status: {existing_podcast.status}")
                return

            publication_date = entry.get('published_parsed')
            if publication_date:
                publication_date = datetime(*publication_date[:6])
                logger.debug(f"  Publication date: {publication_date}")
            else:
                logger.debug("  No publication date found")

            # Create new podcast record
            podcast = Podcasts(
                title=title,
                url=link_url,
                enclosure_url=enclosure_url,
                publication_date=publication_date,
                podcast_feed_name=feed_name,
                status='new'
            )
            db.add(podcast)
            db.commit()

            logger.info(f"Created new podcast record: {title} from {feed_name}")
            logger.debug(f"  New podcast ID: {podcast.id}")

        except Exception as e:
            logger.error(f"Error creating podcast record for {title}: {e}", exc_info=True)
            logger.error(f"  Failed data - title: {title}, url: {link_url}, enclosure: {enclosure_url}")
            db.rollback()
        finally:
            db.close()

def run_podcast_scraper(debug: bool = False):
    """Initializes and runs the podcast RSS scraper."""
    scraper = PodcastRSSScraper(debug=debug)
    scraper.scrape()

if __name__ == '__main__':
    import sys
    debug_mode = '--debug' in sys.argv
    run_podcast_scraper(debug=debug_mode)