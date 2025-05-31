import praw
from typing import List, Dict
from datetime import datetime
from urllib.parse import urlparse

from app.config import settings, logger
from ..queue import process_link_task


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
        
        logger.error(f"Missing Reddit configuration: {', '.join(missing)}")
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
        logger.error(f"Error fetching Reddit posts for {subreddit_name}: {e}", exc_info=True)
        return []




def process_reddit_articles(subreddit_name: str = "front", limit: int = 25, time_filter: str = "day") -> Dict[str, int]:
    """
    Main function to process Reddit articles:
    1. Fetch posts from Reddit
    2. Extract external links
    3. Add links to processing queue
    
    Args:
        subreddit_name: Name of subreddit or "front" for front page
        limit: Maximum number of posts to process
        time_filter: Time filter for top posts (hour, day, week, month, year, all)
    
    Returns:
        Dictionary with processing statistics
    """
    stats = {
        "total_posts": 0,
        "external_links": 0,
        "queued_links": 0,
        "errors": 0
    }
    
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
    
    # Queue each external link for processing
    for i, post in enumerate(external_posts, 1):
        logger.info(f"Queuing link {i}/{len(external_posts)}: {post['url']}")
        
        try:
            # Add link to processing queue
            process_link_task(post["url"], f"reddit-{subreddit_name}")
            stats["queued_links"] += 1
            logger.info(f"Queued link for processing: {post['url']}")
            
        except Exception as e:
            logger.error(f"Error queuing link {post['url']}: {e}", exc_info=True)
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
        logger.error(f"Error in fetch_frontpage_posts: {e}", exc_info=True)
        return []
