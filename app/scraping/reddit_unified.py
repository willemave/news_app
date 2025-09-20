from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
import yaml

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import ContentType
from app.scraping.base import BaseScraper

REDDIT_USER_AGENT = "linux:news_app.scraper:v1.0 (by /u/willemaw)"

logger = get_logger(__name__)
settings = get_settings()
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "reddit.yml"


class RedditUnifiedScraper(BaseScraper):
    """Unified scraper for Reddit using the new architecture."""

    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_PATH):
        super().__init__("Reddit")
        resolved_path = Path(config_path)
        if not resolved_path.is_absolute():
            resolved_path = PROJECT_ROOT / resolved_path
        self.config_path = resolved_path
        self.subreddits = self._load_subreddit_config()

    def _load_subreddit_config(self) -> dict[str, int]:
        """Load subreddit configuration from YAML file."""
        config_path = self.config_path

        if not config_path.exists():
            logger.warning(f"Reddit config file not found: {config_path}")
            return {}

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            subreddits_list = config.get("subreddits", [])
            subreddits = {}

            # Convert list format to dict
            for sub in subreddits_list:
                if isinstance(sub, dict) and "name" in sub and "limit" in sub:
                    name = sub["name"]
                    limit = sub["limit"]
                    if isinstance(limit, int) and limit > 0:
                        subreddits[name] = limit
                    else:
                        logger.warning(f"Invalid limit for subreddit {name}: {limit}")
                        subreddits[name] = 10  # Default to 10 if invalid

            logger.info(f"Loaded {len(subreddits)} subreddits from config")
            return subreddits

        except Exception as e:
            logger.error(f"Error loading Reddit config: {e}")
            return {}

    def scrape(self) -> list[dict[str, Any]]:
        """Scrape Reddit posts from multiple subreddits."""
        all_items = []

        # Check if we have Reddit API credentials
        if not self._validate_reddit_config():
            logger.warning("Reddit API credentials not configured, skipping Reddit scraper")
            return []

        with httpx.Client() as client:
            for subreddit_name, limit in self.subreddits.items():
                try:
                    items = self._scrape_subreddit(client, subreddit_name, limit)
                    all_items.extend(items)
                    logger.info(f"Scraped {len(items)} items from r/{subreddit_name}")
                except Exception as e:
                    logger.error(f"Error scraping r/{subreddit_name}: {e}")
                    continue

        logger.info(f"Total Reddit items scraped: {len(all_items)}")
        return all_items

    def _scrape_subreddit(
        self, client: httpx.Client, subreddit_name: str, limit: int
    ) -> list[dict[str, Any]]:
        """Scrape a specific subreddit."""
        items = []

        try:
            # Use Reddit JSON API (no authentication required for public posts)
            if subreddit_name == "front":
                url = "https://www.reddit.com/.json"
            else:
                url = f"https://www.reddit.com/r/{subreddit_name}/new.json"

            params = {"limit": min(limit, 100)}  # Reddit API limit

            response = client.get(
                url,
                params=params,
                headers={"User-Agent": REDDIT_USER_AGENT},
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

                normalized_url = self._normalize_url(post["url"])
                discussion_url = f"https://reddit.com{post.get('permalink', '')}"

                item = {
                    "url": normalized_url,
                    "title": post.get("title"),
                    "content_type": ContentType.NEWS,
                    "is_aggregate": False,
                    "metadata": {
                        "platform": "reddit",  # Scraper identifier
                        "source": post.get("subreddit", subreddit_name),
                        "items": [
                            {
                                "title": post.get("title"),
                                "url": normalized_url,
                                "summary": None,
                                "source": post.get("domain"),
                                "author": post.get("author"),
                                "score": post.get("score", 0),
                                "comments_url": discussion_url,
                                "metadata": {
                                    "score": post.get("score", 0),
                                    "comments": post.get("num_comments", 0),
                                    "upvote_ratio": post.get("upvote_ratio"),
                                    "reddit_id": post.get("id"),
                                },
                            }
                        ],
                        "primary_url": discussion_url,
                        "excerpt": post.get("selftext"),
                        "scraped_at": datetime.utcnow().isoformat(),
                    },
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
        reddit_domains = ["reddit.com", "www.reddit.com", "old.reddit.com", "redd.it"]

        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)

            # Must have a valid domain and not be a Reddit domain
            return bool(parsed.netloc and parsed.scheme in ["http", "https"]) and not any(
                domain in parsed.netloc for domain in reddit_domains
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
