import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from ..database import SessionLocal
from ..models import Links, FailurePhase
from ..queue import process_link_task
from ..config import logger
from ..utils.failures import record_failure

def fetch_hackernews_homepage() -> str:
    """
    Fetch the HTML content of the HackerNews homepage.
    Returns the raw HTML content.
    """
    try:
        response = requests.get("https://news.ycombinator.com/", timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        error_msg = f"Error fetching HackerNews homepage: {e}"
        logger.error(error_msg, exc_info=True)
        record_failure(FailurePhase.scraper, error_msg)
        return ""

def extract_article_links(homepage_html: str) -> List[str]:
    """
    Parse the HackerNews homepage HTML and extract article URLs.
    Returns a list of article URLs.
    """
    try:
        soup = BeautifulSoup(homepage_html, "html.parser")
        article_links = []
        
        # HackerNews structure: look for links with class "titleline"
        titleline_elements = soup.find_all("span", class_="titleline")
        
        for titleline in titleline_elements:
            link_element = titleline.find("a")
            if link_element and link_element.get("href"):
                href = link_element.get("href")
                
                # Handle relative URLs (HN internal links start with "item?id=")
                if href.startswith("item?id="):
                    # Skip HN internal discussion links
                    continue
                elif href.startswith("http"):
                    # External link - this is what we want
                    article_links.append(href)
                
        return article_links
    except Exception as e:
        error_msg = f"Error extracting article links: {e}"
        logger.error(error_msg, exc_info=True)
        record_failure(FailurePhase.scraper, error_msg)
        return []


def create_link_record(url: str, source: str) -> Optional[Tuple[int, bool]]:
    """
    Create a link record in the database if it doesn't exist.
    
    Args:
        url: URL to create record for
        source: Source of the link
        
    Returns:
        A tuple (link_id: int, created: bool) if successful, None otherwise.
        'created' is True if a new record was made, False if it already existed.
    """
    from ..models import Articles
    
    db = SessionLocal()
    try:
        # Check if URL already exists in Articles table (successfully processed)
        existing_article = db.query(Articles).filter(Articles.url == url).first()
        if existing_article:
            logger.info(f"URL already processed as article: {url}")
            return None  # Don't queue if already processed
        
        # Check if link already exists in Links table
        existing_link = db.query(Links).filter(Links.url == url).first()
        if existing_link:
            from ..models import LinkStatus
            logger.info(f"Link {existing_link.id} already exists with status {existing_link.status.value}: {url}")
            return existing_link.id, False # Not created, already exists
        
        # Create new link
        link = Links(url=url, source=source)
        db.add(link)
        db.commit()
        db.refresh(link)
        
        logger.info(f"Created new link record {link.id} for: {url}")
        return link.id, True # Created new
        
    except Exception as e:
        logger.error(f"Error creating link record for {url}: {e}", exc_info=True)
        db.rollback()
        return None
    finally:
        db.close()


def process_hackernews_articles() -> Dict[str, int]:
    """
    Main function to process HackerNews articles:
    1. Fetch homepage
    2. Extract article links
    3. Create link records and queue for processing
    
    Returns a dictionary with processing statistics.
    """
    stats = {
        "total_links": 0,
        "created_links": 0,
        "queued_links": 0,
        "errors": 0
    }
    
    logger.info("Starting HackerNews link discovery...")
    
    # Fetch homepage
    homepage_html = fetch_hackernews_homepage()
    if not homepage_html:
        error_msg = "Failed to fetch HackerNews homepage"
        logger.error(error_msg)
        record_failure(FailurePhase.scraper, error_msg)
        return stats
    
    # Extract article links
    article_links = extract_article_links(homepage_html)
    stats["total_links"] = len(article_links)
    logger.info(f"Found {len(article_links)} article links")
    
    # Create link records and queue for processing
    for i, article_url in enumerate(article_links, 1):
        logger.info(f"Processing link {i}/{len(article_links)}: {article_url}")
        
        try:
            # Create link record if it doesn't exist
            link_record_result = create_link_record(article_url, "hackernews")
            
            if link_record_result is None:
                # URL already processed as article, skip completely
                logger.info(f"URL already processed, skipping: {article_url}")
                continue
            elif link_record_result:
                link_id, created_new = link_record_result
                if created_new:
                    stats["created_links"] += 1
                    # Queue link for processing only if it's new
                    process_link_task(link_id)
                    stats["queued_links"] += 1
                    logger.info(f"Queued new link {link_id} for processing: {article_url}")
                else:
                    # Link already existed - check if it needs retry
                    from ..models import LinkStatus
                    db = SessionLocal()
                    try:
                        existing_link = db.query(Links).filter(Links.id == link_id).first()
                        if existing_link and existing_link.status in [LinkStatus.failed, LinkStatus.new]:
                            # Only queue failed or unprocessed links for retry
                            process_link_task(link_id)
                            stats["queued_links"] += 1
                            logger.info(f"Queued existing link {link_id} for retry (status: {existing_link.status.value}): {article_url}")
                        else:
                            # Link already processed/skipped, don't queue
                            status_str = existing_link.status.value if existing_link else "unknown"
                            logger.info(f"Skipping existing link {link_id} (status: {status_str}): {article_url}")
                    finally:
                        db.close()
            else: # Error during create_link_record
                stats["errors"] += 1
            
        except Exception as e:
            error_msg = f"Error processing link {article_url}: {e}"
            logger.error(error_msg, exc_info=True)
            record_failure(FailurePhase.scraper, error_msg)
            stats["errors"] += 1
    
    logger.info(f"HackerNews link discovery completed. Stats: {stats}")
    return stats
