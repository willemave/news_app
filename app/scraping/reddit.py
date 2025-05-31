import praw
from typing import List, Dict, Optional
from datetime import datetime
from urllib.parse import urlparse
import logging # Import logging

from app.config import settings, logger # Import logger from config
from .aggregator import scrape_url
from app.llm import summarize_article
from ..database import SessionLocal
from ..models import Articles, Summaries, ArticleStatus


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
            logger.info(f"Fetching 'top' posts from r/{subreddit_name} (limit={limit}, time_filter='{time_filter}').")
            subreddit = reddit.subreddit(subreddit_name)
            submissions = subreddit.top(time_filter=time_filter, limit=limit)
        
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


def scrape_reddit_article(post_data: Dict[str, str]) -> Optional[Dict[str, str]]:
    """
    Scrape content from a Reddit post's external URL.
    
    Args:
        post_data: Dictionary containing post information from fetch_reddit_posts
    
    Returns:
        Dictionary with scraped content or None if failed
    """
    try:
        # Use the aggregator to scrape the external URL
        scraped_content = scrape_url(post_data["url"])
        
        if not scraped_content or not scraped_content.get("content"):
            logger.warning(f"Failed to scrape content from {post_data['url']}")
            return None
        
        # Basic content validation
        content = scraped_content.get("content", "").strip()
        if len(content) < 100: # Arbitrary threshold for minimal content length
            logger.warning(f"Content too short for {post_data['url']}. Length: {len(content)}")
            return None
        
        return {
            "url": post_data["url"],
            "title": scraped_content.get("title") or post_data["title"],
            "author": scraped_content.get("author") or post_data.get("author"),
            "publication_date": scraped_content.get("publication_date") or post_data.get("created_utc"),
            "raw_content": content,
            "reddit_metadata": {
                "score": post_data.get("score"),
                "num_comments": post_data.get("num_comments"),
                "subreddit": post_data.get("subreddit"),
                "permalink": post_data.get("permalink")
            }
        }
    
    except Exception as e:
        logger.error(f"Error scraping Reddit article {post_data['url']}: {e}", exc_info=True)
        return None


def process_reddit_articles(subreddit_name: str = "front", limit: int = 25, time_filter: str = "day") -> Dict[str, int]:
    """
    Main function to process Reddit articles:
    1. Fetch posts from Reddit
    2. Scrape external article content
    3. Summarize content
    4. Store in database
    
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
        "successful_scrapes": 0,
        "successful_summaries": 0,
        "errors": 0,
        "duplicates_skipped": 0
    }
    
    logger.info(f"Starting Reddit scraping process for subreddit '{subreddit_name}', limit={limit}, time_filter='{time_filter}'.")
    
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
    
    # Get database session
    db = SessionLocal()
    
    try:
        for i, post in enumerate(external_posts, 1):
            logger.info(f"Processing article {i}/{len(external_posts)}: {post['url']}")
            
            # Check if article already exists
            existing_article = db.query(Articles).filter(Articles.url == post["url"]).first()
            if existing_article:
                logger.info(f"Article already exists, skipping: {post['url']}")
                stats["duplicates_skipped"] += 1
                continue
            
            # Scrape article content
            article_data = scrape_reddit_article(post)
            if not article_data:
                stats["errors"] += 1
                continue
            
            stats["successful_scrapes"] += 1
            
            # Create Article record
            article = Articles(
                title=article_data["title"],
                url=article_data["url"],
                author=article_data.get("author"),
                publication_date=article_data.get("publication_date"),
                raw_content=article_data["raw_content"],
                scraped_date=datetime.utcnow(),
                status=ArticleStatus.scraped
            )
            
            db.add(article)
            db.flush()  # Get the article ID
            
            # Generate summary
            try:
                summaries = summarize_article(article_data["raw_content"])
                
                # Handle both old and new summarize_article return formats
                if isinstance(summaries, dict):
                    short_summary = summaries.get("short", "")
                    detailed_summary = summaries.get("detailed", "")
                else:
                    # Fallback for tuple format
                    short_summary = summaries[0] if len(summaries) > 0 else ""
                    detailed_summary = summaries[1] if len(summaries) > 1 else ""
                
                # Create Summary record
                summary = Summaries(
                    article_id=article.id,
                    short_summary=short_summary,
                    detailed_summary=detailed_summary,
                    summary_date=datetime.utcnow()
                )
                
                db.add(summary)
                
                # Update article status to processed
                article.status = ArticleStatus.processed
                
                stats["successful_summaries"] += 1
                logger.info(f"Successfully processed and summarized: {article_data['title']}")
                
            except Exception as e:
                logger.error(f"Error generating summary for {post['url']}: {e}", exc_info=True)
                stats["errors"] += 1
                # Keep article as scraped even if summary fails
            
            # Commit after each article to avoid losing progress
            db.commit()
    
    except Exception as e:
        logger.error(f"Critical error in process_reddit_articles for {subreddit_name}: {e}", exc_info=True)
        db.rollback()
        stats["errors"] += 1
    
    finally:
        db.close()
    
    logger.info(f"Reddit scraping completed for {subreddit_name}. Stats: {stats}")
    return stats


# Legacy function for backward compatibility
def fetch_frontpage_posts(limit: int = 100) -> List[Dict[str, str]]:
    """
    Legacy function for backward compatibility.
    Fetch top posts from Reddit's front page and summarize their content.
    
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
            if submission.is_self:
                content = submission.selftext or ""
            else:
                scraped = scrape_url(submission.url)
                content = scraped.get("content", "") if scraped else ""

            if content:
                summaries = summarize_article(content)
                
                # Handle both dict and tuple return formats
                if isinstance(summaries, dict):
                    short_sum = summaries.get("short", "")
                    detailed_sum = summaries.get("detailed", "")
                else:
                    short_sum = summaries[0] if len(summaries) > 0 else ""
                    detailed_sum = summaries[1] if len(summaries) > 1 else ""
                
                results.append({
                    "title": submission.title,
                    "url": submission.url,
                    "short_summary": short_sum,
                    "detailed_summary": detailed_sum,
                })
        
        return results
    
    except Exception as e:
        logger.error(f"Error in fetch_frontpage_posts: {e}", exc_info=True)
        return []
