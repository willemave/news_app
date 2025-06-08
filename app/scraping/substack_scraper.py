import feedparser
import yaml
import re
import os
from typing import List
from datetime import datetime
from app.database import SessionLocal
from app.models import Links, Articles
from app.config import logger

def sanitize_filename(title: str) -> str:
    """Sanitizes a title to be a valid filename."""
    # Remove invalid characters
    sanitized = re.sub(r'[^\w\s-]', '', title).strip()
    # Replace spaces with hyphens
    sanitized = re.sub(r'[-\s]+', '-', sanitized)
    # Truncate to a reasonable length
    return sanitized[:100]

def load_substack_feeds(config_path: str = 'config/substack.yml') -> List[str]:
    """Loads Substack feed URLs from a YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        feeds = config.get('feeds', [])
        # Extract URLs from the feed list
        return [feed.get('url') if isinstance(feed, dict) else feed for feed in feeds if feed]
    except FileNotFoundError:
        logger.error(f"Substack config file not found at: {config_path}")
        return []
    except Exception as e:
        logger.error(f"Error loading Substack config: {e}", exc_info=True)
        return []

class SubstackScraper:
    def __init__(self, config_path: str = 'config/substack.yml'):
        self.feeds = load_substack_feeds(config_path)
        self.podcast_filter = re.compile(r'\b(podcast|transcript)\b', re.IGNORECASE)

    def scrape(self):
        """Scrapes all configured Substack feeds."""
        if not self.feeds:
            logger.warning("No Substack feeds configured. Skipping scrape.")
            return

        for feed_url in self.feeds:
            if not feed_url:
                logger.warning("Skipping empty feed URL.")
                continue

            logger.info(f"Scraping Substack feed: {feed_url}")
            try:
                parsed_feed = feedparser.parse(feed_url)
                if parsed_feed.bozo:
                    logger.warning(f"Feed {feed_url} may be ill-formed: {parsed_feed.bozo_exception}")
                
                # Extract feed name and description from the RSS feed
                feed_name = parsed_feed.feed.get('title', 'Unknown Feed')
                feed_description = parsed_feed.feed.get('description', '')
                
                logger.info(f"Processing feed: {feed_name} - {feed_description}")
                
                for entry in parsed_feed.entries:
                    self.process_entry(entry, feed_name, feed_description)

            except Exception as e:
                logger.error(f"Error scraping feed {feed_url}: {e}", exc_info=True)

    def process_entry(self, entry, feed_name: str, feed_description: str = ""):
        """Processes a single entry from an RSS feed."""
        title = entry.get('title', 'No Title')
        link = entry.get('link')

        if not link:
            logger.warning(f"Skipping entry with no link in feed {feed_name}: {title}")
            return

        # Filter out podcasts
        if self.podcast_filter.search(title):
            logger.info(f"Skipping podcast entry: {title}")
            return

        # Save content and create link record
        self.save_article_and_create_link(entry, feed_name, feed_description)

    def save_article_and_create_link(self, entry, feed_name: str, feed_description: str = ""):
        """Saves the article content and creates a link record in the DB."""
        title = entry.get('title', 'No Title')
        link_url = entry.get('link')
        content = ""
        if 'content' in entry and entry['content']:
            for c in entry['content']:
                if c.get('type') == 'text/html':
                    content = c.get('value', '')
                    break
        if not content:
            content = entry.get('summary', '')

        # 1. Save content to file
        sanitized_title = sanitize_filename(title)
        filename = f"{sanitized_title}.md"
        dir_path = "data/substack"
        os.makedirs(dir_path, exist_ok=True)
        file_path = os.path.join(dir_path, filename)

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.info(f"Saved article content to: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save article {title} to {file_path}: {e}", exc_info=True)
            return

        # 2. Create link record in DB
        db = SessionLocal()
        try:
            # Check if URL already exists in Articles table
            existing_article = db.query(Articles).filter(Articles.url == link_url).first()
            if existing_article:
                logger.info(f"URL already processed as article, skipping: {link_url}")
                return

            # Check if link already exists
            existing_link = db.query(Links).filter(Links.url == link_url).first()
            if existing_link:
                logger.info(f"Link already exists, skipping: {link_url}")
                return

            # Create new link and article record directly.
            # This is a specific workflow for Substack where content is pre-downloaded.
            new_link = Links(url=link_url, source='substack')
            db.add(new_link)
            db.commit()
            db.refresh(new_link)

            publication_date = entry.get('published_parsed')
            if publication_date:
                publication_date = datetime(*publication_date[:6])

            # The processor will look for articles with a 'new' status to summarize.
            article = Articles(
                title=title,
                url=link_url,
                author=entry.get('author'),
                publication_date=publication_date,
                link_id=new_link.id,
                local_path=file_path,
                status='new'
            )
            db.add(article)
            db.commit()

            logger.info(f"Created new link and article for: {link_url} with local path {file_path}")
            # No need to queue a task, a separate worker will process 'new' articles.

        except Exception as e:
            logger.error(f"Error creating DB record for {link_url}: {e}", exc_info=True)
            db.rollback()
        finally:
            db.close()

def run_substack_scraper():
    """Initializes and runs the Substack scraper."""
    scraper = SubstackScraper()
    scraper.scrape()

if __name__ == '__main__':
    run_substack_scraper()