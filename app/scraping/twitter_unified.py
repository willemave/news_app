from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import json
from urllib.parse import urlparse

import yaml
import jmespath
from playwright.sync_api import Response, sync_playwright

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.metadata import ContentType
from app.models.schema import Content
from app.scraping.base import BaseScraper

logger = get_logger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "twitter.yml"


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
        config_path = CONFIG_PATH

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
                items = self._scrape_list_playwright(list_config)
                if items:
                    all_items.extend(items)
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

    def _scrape_list_playwright(self, list_config: dict[str, Any]) -> list[dict[str, Any]] | None:
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
                            decoded = self._decode_response_json(call)
                            if not decoded:
                                continue

                            data, payload_size = decoded
                            logger.info(
                                "Processing API response from %s... (~%s chars)",
                                call.url[:50],
                                payload_size,
                            )
                            
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
                        logger.warning(
                            "Error processing API response from %s: %s",
                            call.url[:50],
                            e,
                        )
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
        
        news_entries: list[dict[str, Any]] = []
        seen_pairs: set[tuple[str, str]] = set()

        for tweet in tweets:
            links = tweet.get("links", [])
            if not links:
                continue

            for link in links:
                article_url = link.get("expanded_url") or link.get("url")
                if not article_url:
                    continue

                normalized_article_url = self._normalize_external_url(article_url)
                if not normalized_article_url:
                    continue

                unique_key = (normalized_article_url, str(tweet.get("id")))
                if unique_key in seen_pairs:
                    continue
                seen_pairs.add(unique_key)

                domain = self._extract_domain(normalized_article_url)
                headline = tweet.get("content", "").split("\n", 1)[0].strip()
                display_title = headline or link.get("title") or normalized_article_url

                metadata = {
                    "platform": "twitter",
                    "source": domain,
                    "article": {
                        "url": normalized_article_url,
                        "title": display_title,
                        "source_domain": domain,
                    },
                    "aggregator": {
                        "name": "Twitter",
                        "title": tweet.get("content", "").strip(),
                        "url": tweet.get("url"),
                        "external_id": str(tweet.get("id")),
                        "author": tweet.get("display_name"),
                        "metadata": {
                            "username": tweet.get("username"),
                            "likes": tweet.get("likes"),
                            "retweets": tweet.get("retweets"),
                            "replies": tweet.get("replies"),
                            "quotes": tweet.get("quotes"),
                            "tweet_created_at": tweet.get("created_at"),
                            "list_id": list_id,
                            "list_name": list_name,
                            "hours_back": hours_back,
                        },
                    },
                    "discovery_time": datetime.now(timezone.utc).isoformat(),
                }

                news_entries.append(
                    {
                        "url": normalized_article_url,
                        "title": display_title[:280],
                        "content_type": ContentType.NEWS,
                        "is_aggregate": False,
                        "metadata": metadata,
                    }
                )

        return news_entries or None

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
            normalized = self._normalize_tweet_result(tweet_result)
            if not normalized:
                continue

            legacy_data = normalized.get("legacy", {})
            user_data = normalized.get("user", {})

            # Skip if no text content
            content_value = legacy_data.get("full_text") or legacy_data.get("text")
            if not content_value:
                continue

            tweet_id = legacy_data.get("id_str") or legacy_data.get("id") or normalized.get("rest_id", "")
            username = user_data.get("screen_name") or user_data.get("username") or "unknown"

            processed_tweet = {
                "id": str(tweet_id),
                "url": f"https://twitter.com/{username}/status/{tweet_id}",
                "date": legacy_data.get("created_at", ""),
                "username": username,
                "display_name": user_data.get("name", "Unknown User"),
                "content": content_value,
                "likes": legacy_data.get("favorite_count", 0),
                "retweets": legacy_data.get("retweet_count", 0),
                "replies": legacy_data.get("reply_count", 0),
                "quotes": legacy_data.get("quote_count", 0),
                "created_at": legacy_data.get("created_at", ""),
                "is_retweet": bool(
                    legacy_data.get("retweeted_status_result") or legacy_data.get("retweeted_status")
                ),
                "in_reply_to_status_id": legacy_data.get("in_reply_to_status_id_str")
                or legacy_data.get("in_reply_to_status_id"),
                "links": self._extract_external_links(legacy_data),
            }
            processed_tweets.append(processed_tweet)

        return processed_tweets

    def _decode_response_json(self, response: Response) -> tuple[Any, int] | None:
        """Safely decode JSON payloads captured by Playwright responses."""

        url = response.url

        if response.status != 200:
            logger.debug("Skipping non-success response from %s (status %s)", url, response.status)
            return None

        content_type = (response.header_value("content-type") or "").lower()
        should_attempt = (
            "json" in content_type
            or "graphql" in url.lower()
            or url.lower().endswith(".json")
        )

        if not should_attempt:
            logger.debug(
                "Skipping response from %s due to content-type '%s'",
                url,
                content_type or "unknown",
            )
            return None

        try:
            body_text = response.text()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Unable to read response body from %s: %s", url, exc)
            return None

        if not body_text.strip():
            logger.debug("Skipping empty response body from %s", url)
            return None

        try:
            data = json.loads(body_text)
        except json.JSONDecodeError as exc:
            logger.info("JSON decode failed for %s: %s", url, exc)
            return None

        return data, len(body_text)

    def _normalize_tweet_result(self, tweet_result: dict[str, Any]) -> dict[str, Any] | None:
        """Normalize tweet payloads from GraphQL responses into a consistent shape."""
        if not tweet_result or not isinstance(tweet_result, dict):
            return None

        current: dict[str, Any] | None = tweet_result
        max_depth = 6
        depth = 0

        while isinstance(current, dict) and depth < max_depth:
            typename = current.get("__typename")
            if typename == "TweetTombstone":
                return None

            if "tweet" in current and isinstance(current["tweet"], dict):
                current = current["tweet"]
                depth += 1
                continue

            if "result" in current and isinstance(current["result"], dict):
                current = current["result"]
                depth += 1
                continue

            break

        if not isinstance(current, dict):
            return None

        legacy_data = current.get("legacy")
        if not isinstance(legacy_data, dict):
            if "full_text" in current or "text" in current:
                legacy_data = current
            else:
                return None

        core_data = current.get("core", {})
        user_results = core_data.get("user_results", {}).get("result", {})
        if isinstance(user_results, dict) and "legacy" in user_results:
            user_data = user_results["legacy"]
        elif isinstance(user_results, dict):
            user_data = user_results
        else:
            user_data = {}

        if not user_data and isinstance(legacy_data.get("user"), dict):
            user_data = legacy_data["user"]

        if not user_data and isinstance(current.get("author"), dict):
            user_data = current["author"].get("legacy", {}) or current["author"].get("result", {})

        rest_id = current.get("rest_id") or legacy_data.get("id_str") or legacy_data.get("id")

        return {
            "legacy": legacy_data,
            "core": core_data,
            "user": user_data,
            "rest_id": rest_id,
        }

    def _extract_external_links(self, legacy_data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract expanded external links from tweet entities."""

        if not isinstance(legacy_data, dict):
            return []

        urls = legacy_data.get("entities", {}).get("urls", [])
        links: list[dict[str, Any]] = []

        for url_info in urls:
            if not isinstance(url_info, dict):
                continue
            expanded = url_info.get("expanded_url") or url_info.get("unwound_url") or url_info.get("url")
            if not expanded:
                continue
            normalized = self._normalize_external_url(expanded)
            if not normalized:
                continue
            links.append(
                {
                    "url": url_info.get("url"),
                    "expanded_url": normalized,
                    "display_url": url_info.get("display_url"),
                }
            )

        return links

    def _normalize_external_url(self, url: str) -> str | None:
        try:
            parsed = urlparse(url)
        except Exception:
            return None

        if not parsed.netloc:
            return None

        domain = parsed.netloc.lower()
        if domain.endswith("twitter.com") or domain.endswith("t.co"):
            return None

        scheme = parsed.scheme or "https"
        normalized = parsed._replace(scheme=scheme)
        url_str = normalized.geturl()
        if url_str.startswith("http://"):
            url_str = "https://" + url_str[len("http://") :]
        return url_str

    def _extract_domain(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return ""
    
    def _parse_tweet_date(self, date_str: str) -> datetime | None:
        """Parse Twitter's date format to datetime."""
        if not date_str:
            return None

        try:
            # Twitter date format: "Wed Oct 05 20:17:27 +0000 2022"
            return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
        except Exception:
            return None
