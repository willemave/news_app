from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import hashlib

import yaml
import jmespath
from playwright.sync_api import sync_playwright

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.metadata import ContentType
from app.models.schema import Content
from app.scraping.base import BaseScraper

logger = get_logger(__name__)


class TwitterUnifiedScraper(BaseScraper):
    """Playwright-based Twitter scraper for lists and searches."""

    def __init__(self):
        super().__init__("Twitter")
        self.config = self._load_config()
        self.settings = self.config.get("settings", {})
        # You can configure proxy here if needed
        self.proxy = self.settings.get("proxy")  # Format: "http://user:pass@host:port"

    def _load_config(self) -> dict[str, Any]:
        """Load Twitter configuration from YAML file."""
        config_path = Path("config/twitter.yml")

        if not config_path.exists():
            logger.warning(f"Twitter config file not found: {config_path}")
            return {"twitter_searches": [], "twitter_lists": [], "settings": {}}

        try:
            with open(config_path) as f:
                config = yaml.safe_load(f)

            searches = len(config.get("twitter_searches", []))
            lists = len(config.get("twitter_lists", []))
            logger.info(f"Loaded {searches} searches and {lists} lists from Twitter config")
            return config

        except Exception as e:
            logger.error(f"Error loading Twitter config: {e}")
            return {"twitter_searches": [], "twitter_lists": [], "settings": {}}

    def scrape(self) -> list[dict[str, Any]]:
        """Scrape Twitter lists using Playwright."""
        all_items = []

        # Check if we have any configuration
        has_lists = bool(self.config.get("twitter_lists"))
        
        if not has_lists:
            logger.warning("No Twitter lists configured")
            return []

        # Scrape lists using Playwright
        for list_config in self.config.get("twitter_lists", []):
            try:
                item = self._scrape_list_playwright(list_config)
                if item:
                    all_items.append(item)
                    logger.info(f"Scraped Twitter list: {list_config.get('name')}")
            except Exception as e:
                logger.error(f"Error scraping Twitter list {list_config.get('name')}: {e}")
                continue

        logger.info(f"Total Twitter list items scraped: {len(all_items)}")
        return all_items

    def _check_recent_scrape(self, list_id: str, list_name: str, hours: int = 6) -> bool:
        """Check if list was scraped recently."""
        with get_db() as db:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
            existing = db.query(Content).filter(
                Content.platform == "twitter",
                Content.source == f"twitter:{list_name}",
                Content.created_at > cutoff_time
            ).first()
            return existing is not None

    def _scrape_list_playwright(self, list_config: dict[str, Any]) -> dict[str, Any] | None:
        """Scrape a Twitter list using Playwright to intercept XHR requests."""
        list_name = list_config.get("name", "Unknown List")
        list_id = list_config.get("list_id")
        limit = list_config.get("limit", self.settings.get("default_limit", 50))
        hours_back = list_config.get("hours_back", self.settings.get("default_hours_back", 24))
        
        if not list_id:
            logger.error(f"No list_id provided for list: {list_name}")
            return None

        # Check if already scraped recently
        if self._check_recent_scrape(list_id, list_name, hours=6):
            logger.info(f"Skipping list {list_name} - already scraped within last 6 hours")
            return None

        logger.info(f"Scraping Twitter list with Playwright: {list_name} ({list_id})")
        
        tweets = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
        
        try:
            with sync_playwright() as pw:
                browser_args = {"headless": True}
                if self.proxy:
                    browser_args["proxy"] = {"server": self.proxy}
                
                browser = pw.chromium.launch(**browser_args)
                page = browser.new_page()
                
                # Set user agent to avoid detection
                page.set_extra_http_headers({
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                })
                
                xhr_calls = []
                
                # Capture Twitter API calls (broader patterns)
                def on_response(response):
                    url = response.url
                    # Look for Twitter API endpoints
                    api_patterns = [
                        "ListLatestTweets", "TweetResultByRestId", "UserTweets", 
                        "HomeTimeline", "SearchTimeline", "ListTweets",
                        "graphql", "api/graphql", "i/api/graphql"
                    ]
                    if any(pattern in url for pattern in api_patterns):
                        xhr_calls.append(response)
                        logger.info(f"Captured API call: {url[:100]}...")
                    elif "twitter.com" in url and ("json" in response.headers.get("content-type", "") or "api" in url):
                        xhr_calls.append(response)
                        logger.info(f"Captured potential API call: {url[:100]}...")
                
                page.on("response", on_response)
                
                # Navigate to the list page
                list_url = f"https://twitter.com/i/lists/{list_id}"
                logger.info(f"Navigating to: {list_url}")
                
                try:
                    # Try to navigate to the list page
                    response = page.goto(list_url, wait_until="domcontentloaded", timeout=15000)
                    logger.info(f"Page response status: {response.status if response else 'No response'}")
                    
                    # Check if we're redirected to login
                    current_url = page.url
                    if "login" in current_url.lower() or "authenticate" in current_url.lower():
                        logger.warning(f"Twitter requires login to access this list. Current URL: {current_url}")
                        raise Exception("Login required - cannot access list without authentication")
                    
                    # Wait for content to load (be more lenient with timeout)
                    try:
                        page.wait_for_selector("[data-testid='tweet'], [data-testid='cellInnerDiv']", timeout=5000)
                        logger.info("Found tweet elements on page")
                    except Exception:
                        logger.warning("Could not find tweet elements, but continuing...")
                    
                    # Give some time for dynamic content to load
                    page.wait_for_timeout(3000)
                    
                    # Try scrolling to trigger more API calls
                    max_scrolls = min(3, (limit // 20) + 1)
                    for i in range(max_scrolls):
                        page.mouse.wheel(0, 2000)
                        page.wait_for_timeout(1500)
                        logger.debug(f"Scroll {i+1}/{max_scrolls}")
                    
                    logger.info(f"Captured {len(xhr_calls)} API responses")
                    
                except Exception as e:
                    logger.warning(f"Error loading Twitter list page: {e}")
                    if "timeout" in str(e).lower():
                        logger.info("Continuing with any captured API calls...")
                    else:
                        raise
                
                # Process captured API responses (before closing browser)
                tweets_from_responses = []
                for call in xhr_calls:
                    try:
                        if call.status == 200:
                            data = call.json()
                            logger.info(f"Processing API response from {call.url[:50]}... with {len(str(data))} characters")
                            
                            list_tweets = self._extract_tweets_from_response(data)
                            logger.info(f"Extracted {len(list_tweets)} tweets from this response")
                            
                            for tweet_data in list_tweets:
                                if len(tweets) >= limit:
                                    break
                                
                                # Parse tweet date
                                tweet_date = self._parse_tweet_date(tweet_data.get("created_at", ""))
                                if tweet_date and tweet_date < cutoff_time:
                                    continue
                                
                                # Apply filters
                                if not self.settings.get("include_retweets", False) and tweet_data.get("is_retweet"):
                                    continue
                                
                                if not self.settings.get("include_replies", False) and tweet_data.get("in_reply_to_status_id"):
                                    continue
                                
                                # Check engagement threshold
                                min_engagement = self.settings.get("min_engagement", 0)
                                likes = tweet_data.get("likes", tweet_data.get("favorite_count", 0))
                                retweets = tweet_data.get("retweets", tweet_data.get("retweet_count", 0))
                                if (likes + retweets) < min_engagement:
                                    continue
                                
                                tweets.append(tweet_data)
                                logger.debug(f"Added tweet from @{tweet_data.get('username', 'unknown')}")
                                
                    except Exception as e:
                        logger.warning(f"Error processing API response from {call.url[:50]}: {e}")
                        continue
                
                # Now close browser after processing responses
                browser.close()
                logger.info(f"Total tweets collected: {len(tweets)}")
        
        except Exception as e:
            logger.error(f"Playwright scraping failed for list {list_id}: {e}")
            return None
        
        if not tweets:
            logger.info(f"No tweets found for list: {list_name}")
            return None
        
        # Create aggregated content
        content = self._format_tweet_content(tweets, list_name)
        
        # Generate unique URL
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        url_hash = hashlib.md5(f"{list_id}_{date_str}".encode()).hexdigest()[:8]
        unique_url = f"twitter://list/{list_id}/{date_str}/{url_hash}"
        
        # Create content item
        item = {
            "url": unique_url,
            "title": f"Twitter List: {list_name} - {date_str}",
            "content_type": ContentType.ARTICLE,
            "metadata": {
                "platform": "twitter",  # Scraper identifier
                # Source uses a domain per convention; list aggregations have no external domain, use twitter.com
                "source": "twitter.com",
                "list_id": list_id,
                "list_name": list_name,
                "tweet_count": len(tweets),
                "tweets": tweets,
                "aggregation_date": date_str,
                "hours_back": hours_back,
                "content": content,
                "scraped_with": "playwright",
            }
        }
        
        return item
    
    def _extract_tweets_from_response(self, data: dict) -> list[dict[str, Any]]:
        """Extract tweet data from Twitter API response using JMESPath."""
        tweets = []
        
        # Modern Twitter GraphQL API queries (updated for 2024/2025)
        queries = [
            # New GraphQL format for list timeline
            "data.list.tweets_timeline.timeline.instructions[].entries[].content.itemContent.tweet_results.result",
            # Alternative list timeline format
            "data.list.tweets_timeline.timeline.instructions[*].entries[*].content.itemContent.tweet_results.result",
            # Timeline entries format
            "data.timeline.timeline.instructions[].entries[].content.itemContent.tweet_results.result",
            # User timeline
            "data.user.result.timeline.timeline.instructions[].entries[].content.itemContent.tweet_results.result",
            # Direct tweet results
            "data.tweetResult.result",
            # Home timeline format
            "data.home.home_timeline_urt.instructions[].entries[].content.itemContent.tweet_results.result"
        ]
        
        for query in queries:
            try:
                results = jmespath.search(query, data)
                if results:
                    if isinstance(results, list):
                        for result in results:
                            if result and isinstance(result, dict):
                                tweets.append(result)
                    elif isinstance(results, dict):
                        tweets.append(results)
            except Exception as e:
                logger.debug(f"Query '{query}' failed: {e}")
                continue
        
        # If no tweets found with specific queries, try generic search
        if not tweets:
            try:
                # Look for any tweet-like objects with legacy data
                generic_results = jmespath.search("**.legacy", data)
                if isinstance(generic_results, list):
                    tweets.extend([r for r in generic_results if r and isinstance(r, dict) and "full_text" in r])
                elif isinstance(generic_results, dict) and "full_text" in generic_results:
                    tweets.append({"legacy": generic_results})
            except Exception:
                pass
        
        # Process tweets to standardize format
        processed_tweets = []
        for tweet_result in tweets:
            if not tweet_result or not isinstance(tweet_result, dict):
                continue
            
            # Handle both new GraphQL format and legacy format
            legacy_data = tweet_result.get("legacy", tweet_result)
            user_data = tweet_result.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
            
            if not user_data and "user" in legacy_data:
                user_data = legacy_data["user"]
            
            # Skip if no text content
            if not legacy_data.get("full_text") and not legacy_data.get("text"):
                continue
            
            processed_tweet = {
                "id": str(legacy_data.get("id_str", legacy_data.get("id", ""))),
                "url": f"https://twitter.com/{user_data.get('screen_name', 'unknown')}/status/{legacy_data.get('id_str', legacy_data.get('id', ''))}",
                "date": legacy_data.get("created_at", ""),
                "username": user_data.get("screen_name", "unknown"),
                "display_name": user_data.get("name", "Unknown User"),
                "content": legacy_data.get("full_text", legacy_data.get("text", "")),
                "likes": legacy_data.get("favorite_count", 0),
                "retweets": legacy_data.get("retweet_count", 0),
                "replies": legacy_data.get("reply_count", 0),
                "quotes": legacy_data.get("quote_count", 0),
                "created_at": legacy_data.get("created_at", ""),
                "is_retweet": "retweeted_status" in legacy_data,
                "in_reply_to_status_id": legacy_data.get("in_reply_to_status_id_str"),
            }
            processed_tweets.append(processed_tweet)
        
        return processed_tweets
    
    def _parse_tweet_date(self, date_str: str) -> datetime | None:
        """Parse Twitter's date format to datetime."""
        if not date_str:
            return None
        
        try:
            # Twitter date format: "Wed Oct 05 20:17:27 +0000 2022"
            return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        except Exception:
            return None
    
    def _format_tweet_content(self, tweets: list[dict[str, Any]], list_name: str) -> str:
        """Format tweets into readable markdown content."""
        lines = []
        
        # Header
        lines.append(f"# Twitter List: {list_name}")
        lines.append(f"\n*{len(tweets)} tweets from the last 24 hours*\n")
        lines.append("---\n")
        
        # Format each tweet
        for i, tweet in enumerate(tweets, 1):
            # Tweet header
            lines.append(f"## {i}. @{tweet['username']} ({tweet['display_name']})")
            
            # Timestamp and engagement
            date_str = tweet.get('date', tweet.get('created_at', ''))
            if date_str:
                try:
                    date = self._parse_tweet_date(date_str)
                    if date:
                        date_str = date.strftime("%Y-%m-%d %H:%M UTC")
                except Exception:
                    pass
            
            lines.append(f"*{date_str} • ❤️ {tweet['likes']} • 🔁 {tweet['retweets']} • 💬 {tweet['replies']}*\n")
            
            # Tweet content
            lines.append(tweet['content'])
            lines.append("")
            
            # Link to original tweet
            lines.append(f"[View on Twitter]({tweet['url']})")
            lines.append("\n---\n")
        
        return "\n".join(lines)
