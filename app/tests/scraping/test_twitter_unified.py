"""Tests for the Twitter unified scraper GraphQL parsing."""

from __future__ import annotations

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
