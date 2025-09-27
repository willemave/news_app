"""Tests for the Twitter unified scraper GraphQL parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class DummyResponse:
    """Simple stand-in for Playwright's response object used in tests."""

    url: str
    status: int
    content_type: str | None
    body: bytes

    def header_value(self, name: str) -> str | None:
        if name.lower() == "content-type" and self.content_type is not None:
            return self.content_type
        return None

    def text(self) -> str:
        return self.body.decode("utf-8", errors="ignore")

from app.scraping.twitter_unified import TwitterUnifiedScraper


def build_sample_graphql_payload() -> dict[str, Any]:
    """Build a minimal GraphQL payload matching TweetWithVisibilityResults."""
    return {
        "data": {
            "list": {
                "tweets_timeline": {
                    "timeline": {
                        "instructions": [
                            {
                                "entries": [
                                    {
                                        "content": {
                                            "itemContent": {
                                                "tweet_results": {
                                                    "result": {
                                                        "__typename": "TweetWithVisibilityResults",
                                                        "tweet": {
                                                            "rest_id": "1234567890",
                                                            "legacy": {
                                                                "id_str": "1234567890",
                                                                "full_text": "Sample tweet body",
                                                                "created_at": "Mon Sep 16 12:34:56 +0000 2025",
                                                                "favorite_count": 42,
                                                                "retweet_count": 7,
                                                                "reply_count": 3,
                                                                "quote_count": 1,
                                                                "entities": {
                                                                    "urls": [
                                                                        {
                                                                            "url": "https://t.co/example",
                                                                            "expanded_url": "http://example.com/story",
                                                                            "display_url": "example.com/story",
                                                                        }
                                                                    ]
                                                                },
                                                            },
                                                            "core": {
                                                                "user_results": {
                                                                    "result": {
                                                                        "legacy": {
                                                                            "screen_name": "news_bot",
                                                                            "name": "News Bot",
                                                                        }
                                                                    }
                                                                }
                                                            },
                                                        },
                                                    }
                                                }
                                            }
                                        }
                                    },
                                    {
                                        "content": {
                                            "itemContent": {
                                                "tweet_results": {
                                                    "result": {
                                                        "__typename": "TweetTombstone"
                                                    }
                                                }
                                            }
                                        }
                                    },
                                ]
                            }
                        ]
                    }
                }
            }
        }
}


def test_extract_tweets_from_visibility_results() -> None:
    """Ensure TweetWithVisibilityResults payloads produce normalized tweets."""
    scraper = TwitterUnifiedScraper()
    payload = build_sample_graphql_payload()

    tweets = scraper._extract_tweets_from_response(payload)

    assert len(tweets) == 1
    tweet = tweets[0]

    assert tweet["id"] == "1234567890"
    assert tweet["username"] == "news_bot"
    assert tweet["display_name"] == "News Bot"
    assert tweet["content"] == "Sample tweet body"
    assert tweet["likes"] == 42
    assert tweet["retweets"] == 7
    assert tweet["links"][0]["expanded_url"] == "https://example.com/story"


def test_extract_tweets_handles_value_wrapped_results() -> None:
    """Ensure depth-first traversal finds tweets hidden under value wrappers."""

    payload: dict[str, Any] = {
        "data": {
            "list": {
                "tweets_timeline": {
                    "timeline": {
                        "instructions": [
                            {
                                "entries": [
                                    {
                                        "content": {
                                            "value": {
                                                "itemContent": {
                                                    "tweet_results": {
                                                        "result": {
                                                            "tweet": {
                                                                "rest_id": "555",
                                                                "legacy": {
                                                                    "id_str": "555",
                                                                    "full_text": "Nested tweet body",
                                                                    "created_at": "Tue Sep 23 09:12:34 +0000 2025",
                                                                    "favorite_count": 10,
                                                                    "retweet_count": 2,
                                                                    "reply_count": 1,
                                                                    "quote_count": 0,
                                                                    "entities": {
                                                                        "urls": [
                                                                            {
                                                                                "url": "https://t.co/example2",
                                                                                "expanded_url": "https://example.org/article",
                                                                                "display_url": "example.org/article",
                                                                            }
                                                                        ]
                                                                    },
                                                                },
                                                                "core": {
                                                                    "user_results": {
                                                                        "result": {
                                                                            "legacy": {
                                                                                "screen_name": "depth_bot",
                                                                                "name": "Depth Bot",
                                                                            }
                                                                        }
                                                                    }
                                                                },
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        }
    }

    scraper = TwitterUnifiedScraper()
    tweets = scraper._extract_tweets_from_response(payload)

    assert len(tweets) == 1
    tweet = tweets[0]

    assert tweet["id"] == "555"
    assert tweet["username"] == "depth_bot"
    assert tweet["content"] == "Nested tweet body"
    assert tweet["links"][0]["expanded_url"] == "https://example.org/article"


def test_decode_response_json_skips_non_json() -> None:
    """Responses without JSON content-type are ignored."""
    scraper = TwitterUnifiedScraper()
    response = DummyResponse(
        url="https://abs.twimg.com/responsive-web/client-web/sh",
        status=200,
        content_type="text/html",
        body=b"<html></html>",
    )

    assert scraper._decode_response_json(response) is None


def test_parse_cookie_json_export() -> None:
    """JSON cookie exports should be normalized for Playwright."""

    scraper = TwitterUnifiedScraper()
    raw = json.dumps(
        [
            {
                "name": "auth_token",
                "value": "abc",
                "domain": ".x.com",
                "path": "/",
                "secure": True,
                "httpOnly": True,
                "sameSite": "None",
                "expires": 2147483647,
            }
        ]
    )

    cookies = scraper._parse_cookie_file(raw)

    assert len(cookies) == 1
    cookie = cookies[0]
    assert cookie["name"] == "auth_token"
    assert cookie["domain"] == ".x.com"
    assert cookie["secure"] is True
    assert cookie["httpOnly"] is True
    assert cookie["sameSite"] == "None"
    assert cookie["expires"] == 2147483647


def test_parse_cookie_netscape_export() -> None:
    """Netscape cookie exports should be accepted as fallback."""

    scraper = TwitterUnifiedScraper()
    raw = """# Netscape HTTP Cookie File
.x.com	TRUE	/	FALSE	2147483647	ct0	csrf-token
.x.com	TRUE	/	TRUE	2147483647	auth_token	token-value
"""

    cookies = scraper._parse_cookie_file(raw)

    assert len(cookies) == 2
    auth_cookie = next(cookie for cookie in cookies if cookie["name"] == "auth_token")
    assert auth_cookie["secure"] is True
    assert auth_cookie["path"] == "/"
    assert auth_cookie["domain"] == ".x.com"


def test_decode_response_json_skips_empty_body() -> None:
    """Empty JSON bodies should not raise parse errors."""
    scraper = TwitterUnifiedScraper()
    response = DummyResponse(
        url="https://api.x.com/1.1/graphql/user_flow.json",
        status=200,
        content_type="application/json",
        body=b"   ",
    )

    assert scraper._decode_response_json(response) is None


def test_decode_response_json_returns_payload() -> None:
    """Valid JSON responses are decoded with size metadata."""
    scraper = TwitterUnifiedScraper()
    body = b'{"data": {"hello": "world"}}'
    response = DummyResponse(
        url="https://api.x.com/1.1/graphql/user_flow.json",
        status=200,
        content_type="application/json",
        body=body,
    )

    decoded = scraper._decode_response_json(response)
    assert decoded is not None
    data, length = decoded
    assert data == {"data": {"hello": "world"}}
    assert length == len(body)
