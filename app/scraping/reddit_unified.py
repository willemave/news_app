from typing import List, Dict, Any, Optional
import httpx
import yaml
from datetime import datetime
from pathlib import Path

from app.scraping.base import BaseScraper
from app.domain.content import ContentType
from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()

class RedditUnifiedScraper(BaseScraper):
    """Unified scraper for Reddit using the new architecture."""
    
    def __init__(self):
        super().__init__("Reddit")
        self.subreddits = self._load_subreddit_config()
    
    def _load_subreddit_config(self) -> Dict[str, int]:
        """Load subreddit configuration from YAML file."""
        config_path = Path("config/reddit.yml")
        
        if not config_path.exists():
            logger.error(f"Reddit config file not found: {config_path}")
            return {}
        
        try:
            with open(config_path, "r") as f:
                config = yaml.safe_load(f)
            
            subreddits = config.get("subreddits", {})
            
            # Validate that all values are integers
            for subreddit, limit in subreddits.items():
                if not isinstance(limit, int) or limit <= 0:
                    logger.warning(f"Invalid limit for subreddit {subreddit}: {limit}")
                    subreddits[subreddit] = 10  # Default to 10 if invalid
            
            logger.info(f"Loaded {len(subreddits)} subreddits from config")
            return subreddits
            
        except Exception as e:
            logger.error(f"Error loading Reddit config: {e}")
            return {}
    
    async def scrape(self) -> List[Dict[str, Any]]:
        """Scrape Reddit posts from multiple subreddits."""
        all_items = []
        
        # Check if we have Reddit API credentials
        if not self._validate_reddit_config():
            logger.warning("Reddit API credentials not configured, skipping Reddit scraper")
            return []
        
        async with httpx.AsyncClient() as client:
            for subreddit_name, limit in self.subreddits.items():
                try:
                    items = await self._scrape_subreddit(client, subreddit_name, limit)
                    all_items.extend(items)
                    logger.info(f"Scraped {len(items)} items from r/{subreddit_name}")
                except Exception as e:
                    logger.error(f"Error scraping r/{subreddit_name}: {e}")
                    continue
        
        logger.info(f"Total Reddit items scraped: {len(all_items)}")
        return all_items
    
    async def _scrape_subreddit(
        self, 
        client: httpx.AsyncClient, 
        subreddit_name: str, 
        limit: int
    ) -> List[Dict[str, Any]]:
        """Scrape a specific subreddit."""
        items = []
        
        try:
            # Use Reddit JSON API (no authentication required for public posts)
            if subreddit_name == "front":
                url = "https://www.reddit.com/.json"
            else:
                url = f"https://www.reddit.com/r/{subreddit_name}/new.json"
            
            params = {"limit": min(limit, 100)}  # Reddit API limit
            
            response = await client.get(
                url,
                params=params,
                headers={"User-Agent": "NewsAggregator/1.0"}
            )
            response.raise_for_status()
            
            data = response.json()
            posts = data.get("data", {}).get("children", [])
            
            for post_data in posts:
                post = post_data.get("data", {})
                
                # Skip self posts and posts without external URLs
                if post.get("is_self") or not self._is_external_url(post.get("url", "")):
                    continue
                
                # Skip deleted/removed posts
                if post.get("removed_by_category") or not post.get("title"):
                    continue
                
                item = {
                    'url': self._normalize_url(post['url']),
                    'title': post.get('title'),
                    'content_type': ContentType.ARTICLE,
                    'metadata': {
                        'source': 'reddit',
                        'subreddit': post.get('subreddit', subreddit_name),
                        'reddit_id': post.get('id'),
                        'reddit_url': f"https://reddit.com{post.get('permalink', '')}",
                        'score': post.get('score', 0),
                        'num_comments': post.get('num_comments', 0),
                        'author': post.get('author'),
                        'created_utc': datetime.fromtimestamp(post.get('created_utc', 0)).isoformat() if post.get('created_utc') else None,
                        'domain': post.get('domain'),
                        'upvote_ratio': post.get('upvote_ratio')
                    }
                }
                
                items.append(item)
                
                if len(items) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"Error fetching from r/{subreddit_name}: {e}")
            
        return items
    
    def _is_external_url(self, url: str) -> bool:
        """Check if URL is external (not a Reddit self-post or internal link)."""
        if not url:
            return False
            
        # Skip Reddit internal links and self posts
        reddit_domains = ['reddit.com', 'www.reddit.com', 'old.reddit.com', 'redd.it']
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            
            # Must have a valid domain and not be a Reddit domain
            return (
                bool(parsed.netloc and parsed.scheme in ['http', 'https']) and
                not any(domain in parsed.netloc for domain in reddit_domains)
            )
        except Exception:
            return False
    
    def _validate_reddit_config(self) -> bool:
        """
        Validate Reddit configuration.
        For the JSON API, we don't need authentication, just a user agent.
        """
        # For now, we'll use the public JSON API which doesn't require authentication
        # If we want to use the full Reddit API later, we can check for:
        # - REDDIT_CLIENT_ID
        # - REDDIT_CLIENT_SECRET  
        # - REDDIT_USER_AGENT
        return True