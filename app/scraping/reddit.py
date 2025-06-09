import praw
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from urllib.parse import urlparse

from app.config import settings, logger, SUBREDDIT_LIMITS
from ..database import SessionLocal
from ..models import Links, FailurePhase
from ..queue import process_link_task
from ..utils.failures import record_failure


def validate_reddit_config() -> bool:
    """Validate that required Reddit API credentials are configured."""
    required_settings = [
        settings.REDDIT_CLIENT_ID,
        settings.REDDIT_CLIENT_SECRET,
        settings.REDDIT_USER_AGENT
    ]
    
    if not all(required_settings):
        missing = []
        if not settings.REDDIT_CLIENT_ID:
            missing.append("REDDIT_CLIENT_ID")
        if not settings.REDDIT_CLIENT_SECRET:
            missing.append("REDDIT_CLIENT_SECRET")
        if not settings.REDDIT_USER_AGENT:
            missing.append("REDDIT_USER_AGENT")
        
        error_msg = f"Missing Reddit configuration: {', '.join(missing)}"
        logger.error(error_msg)
        record_failure(FailurePhase.scraper, error_msg)
        return False
    
    return True


def is_external_url(url: str) -> bool:
    """Check if URL is external (not a Reddit self-post or internal link)."""
    try:
        parsed = urlparse(url)
        # Skip Reddit internal links and self posts
        if parsed.netloc in ['reddit.com', 'www.reddit.com', 'old.reddit.com']:
            return False
        # Must have a valid domain
        return bool(parsed.netloc and parsed.scheme in ['http', 'https'])
    except Exception:
        return False


def fetch_reddit_posts(subreddit_name: str = "front", limit: int = 50, time_filter: str = "day") -> List[Dict[str, str]]:
    """
    Fetch posts from Reddit and return basic post information.
    
    Args:
        subreddit_name: Name of subreddit or "front" for front page
        limit: Maximum number of posts to fetch
        time_filter: Time filter for top posts (hour, day, week, month, year, all)
    
    Returns:
        List of dictionaries containing post information
    """
    if not validate_reddit_config():
        return []
    
    try:
        reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
        )
        
        posts = []
        
        # Get posts from specified source
        if subreddit_name == "front":
            logger.info(f"Fetching 'best' posts from the front page (limit={limit}). 'time_filter' is ignored for front.best().")
            submissions = reddit.front.best(limit=limit)
        else:
            logger.info(f"Fetching 'new' posts from r/{subreddit_name} (limit={limit}).")
            subreddit = reddit.subreddit(subreddit_name)
            submissions = subreddit.new(limit=limit)
        
        for submission in submissions:
            # Skip self posts and internal Reddit links for external content scraping
            if submission.is_self or not is_external_url(submission.url):
                continue
            
            posts.append({
                "title": submission.title,
                "url": submission.url,
                "author": str(submission.author) if submission.author else None,
                "score": submission.score,
                "num_comments": submission.num_comments,
                "created_utc": datetime.fromtimestamp(submission.created_utc),
                "subreddit": str(submission.subreddit),
                "permalink": f"https://reddit.com{submission.permalink}"
            })
        
        return posts
    
    except Exception as e:
        error_msg = f"Error fetching Reddit posts for {subreddit_name}: {e}"
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


def process_reddit_articles(subreddit_name: str = "front", limit: Optional[int] = None, time_filter: str = "day") -> Dict[str, int]:
    """
    Main function to process Reddit articles:
    1. Fetch posts from Reddit
    2. Extract external links
    3. Create link records and queue for processing
    
    Args:
        subreddit_name: Name of subreddit or "front" for front page
        limit: Maximum number of posts to process (uses SUBREDDIT_LIMITS if None)
        time_filter: Time filter for top posts (hour, day, week, month, year, all)
    
    Returns:
        Dictionary with processing statistics
    """
    stats = {
        "total_posts": 0,
        "external_links": 0,
        "created_links": 0,
        "queued_links": 0,
        "errors": 0
    }
    
    # Compute limit from SUBREDDIT_LIMITS if not provided
    if limit is None:
        limit = SUBREDDIT_LIMITS.get(subreddit_name, SUBREDDIT_LIMITS.get("*", 50))
    
    logger.info(f"Starting Reddit link discovery for subreddit '{subreddit_name}', limit={limit}, time_filter='{time_filter}'.")
    
    # Fetch Reddit posts
    posts = fetch_reddit_posts(subreddit_name, limit, time_filter)
    stats["total_posts"] = len(posts)
    
    if not posts:
        logger.info(f"No posts fetched from Reddit for {subreddit_name}.")
        return stats
    
    # Filter for external links
    external_posts = [post for post in posts if is_external_url(post["url"])]
    stats["external_links"] = len(external_posts)
    logger.info(f"Found {len(external_posts)} external links from {len(posts)} total posts for {subreddit_name}.")
    
    # Create link records and queue for processing
    for i, post in enumerate(external_posts, 1):
        logger.info(f"Processing link {i}/{len(external_posts)}: {post['url']}")
        
        try:
            # Create link record if it doesn't exist
            link_record_result = create_link_record(post["url"], f"reddit-{subreddit_name}")

            if link_record_result is None:
                # URL already processed as article, skip completely
                logger.info(f"URL already processed, skipping: {post['url']}")
                continue
            elif link_record_result:
                link_id, created_new = link_record_result
                if created_new:
                    stats["created_links"] += 1
                    # Queue link for processing only if it's new
                    process_link_task(link_id)
                    stats["queued_links"] += 1
                    logger.info(f"Queued new link {link_id} for processing: {post['url']}")
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
                            logger.info(f"Queued existing link {link_id} for retry (status: {existing_link.status.value}): {post['url']}")
                        else:
                            # Link already processed/skipped, don't queue
                            status_str = existing_link.status.value if existing_link else "unknown"
                            logger.info(f"Skipping existing link {link_id} (status: {status_str}): {post['url']}")
                    finally:
                        db.close()
            else: # Error during create_link_record
                stats["errors"] += 1
            
        except Exception as e:
            error_msg = f"Error processing link {post['url']}: {e}"
            logger.error(error_msg, exc_info=True)
            record_failure(FailurePhase.scraper, error_msg)
            stats["errors"] += 1
    
    logger.info(f"Reddit link discovery completed for {subreddit_name}. Stats: {stats}")
    return stats


# Legacy function for backward compatibility
def fetch_frontpage_posts(limit: int = 100) -> List[Dict[str, str]]:
    """
    Legacy function for backward compatibility.
    Fetch top posts from Reddit's front page.
    
    Note: This function is deprecated. Use process_reddit_articles() instead.
    """
    logger.warning("fetch_frontpage_posts() is deprecated. Use process_reddit_articles() instead.")
    
    if not validate_reddit_config():
        return []
    
    try:
        reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
        )

        results = []
        for submission in reddit.front.top(limit=limit):
            # Only return basic info, no content processing
            results.append({
                "title": submission.title,
                "url": submission.url,
                "short_summary": "Legacy function - use process_reddit_articles() instead",
                "detailed_summary": "Legacy function - use process_reddit_articles() instead",
            })
        
        return results
    
    except Exception as e:
        error_msg = f"Error in fetch_frontpage_posts: {e}"
        logger.error(error_msg, exc_info=True)
        record_failure(FailurePhase.scraper, error_msg)
        return []
