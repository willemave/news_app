"""Tests for the Twitter unified scraper GraphQL parsing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import pytest


@dataclass
class DummyRequest:
    """Mimics minimal Playwright Request interface."""

    url: str
    method: str = "GET"
    post_data_value: bytes | str | None = None

    def post_data(self) -> bytes | str | None:
        return self.post_data_value


@dataclass
class DummyResponse:
    """Simple stand-in for Playwright's response object used in tests."""

    url: str
    status: int
    content_type: str | None
    payload: bytes
    request: DummyRequest | None = None

    def header_value(self, name: str) -> str | None:
        if name.lower() == "content-type" and self.content_type is not None:
            return self.content_type
        return None

    def text(self) -> str:
        return self.payload.decode("utf-8", errors="ignore")

    def body(self) -> bytes:
        return self.payload

from app.scraping.twitter_unified import DEFAULT_USER_AGENT, TwitterUnifiedScraper


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
        payload=b"<html></html>",
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
        payload=b"   ",
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
        payload=body,
    )

    decoded = scraper._decode_response_json(response)
    assert decoded is not None
    data, length = decoded
    assert data == {"data": {"hello": "world"}}
    assert length == len(body)


def test_decode_response_json_logs_404_empty_body(caplog: pytest.LogCaptureFixture) -> None:
    """Non-success responses log debug context and return None."""

    scraper = TwitterUnifiedScraper()
    response = DummyResponse(
        url="https://api.x.com/1.1/graphql/user_flow.json",
        status=404,
        content_type="application/json",
        payload=b"",
    )

    with caplog.at_level("DEBUG"):
        assert scraper._decode_response_json(response) is None

    assert any("Skipping non-success response" in message for message in caplog.messages)


def test_decode_response_json_skips_abs_asset_logs(caplog: pytest.LogCaptureFixture) -> None:
    """Static asset responses are ignored with a debug breadcrumb."""

    scraper = TwitterUnifiedScraper()
    response = DummyResponse(
        url="https://abs.twimg.com/responsive-web/client-web/sh",
        status=404,
        content_type="text/html;charset=utf-8",
        payload=b"<html>rate limit</html>",
    )

    with caplog.at_level("DEBUG"):
        assert scraper._decode_response_json(response) is None

    assert any("Skipping asset response" in message for message in caplog.messages)


def test_decode_response_json_logs_transient_429(caplog: pytest.LogCaptureFixture) -> None:
    """Transient rate-limit responses surface a warning preview."""

    scraper = TwitterUnifiedScraper()
    response = DummyResponse(
        url="https://api.x.com/1.1/graphql/user_flow.json",
        status=429,
        content_type="application/json",
        payload=b'{"errors": [{"message": "rate limit"}]}',
        request=DummyRequest(
            url="https://api.x.com/1.1/graphql/user_flow.json",
            method="GET",
        ),
    )

    with caplog.at_level("WARNING"):
        assert scraper._decode_response_json(response) is None

    assert any(
        "retry_failed" in message or "retry_exhausted" in message
        for message in caplog.messages
    )


def test_build_headers_activates_guest_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Guest activation endpoint should be called when no auth cookies are present."""

    scraper = TwitterUnifiedScraper()
    scraper._has_auth_cookies = False

    activation_calls: list[tuple[str, str]] = []

    def fake_request(url: str, method: str, headers: dict[str, str], data: bytes | None) -> tuple[int, str, str]:
        activation_calls.append((url, method))
        return 200, "application/json", json.dumps({"guest_token": "TOKEN123"})

    monkeypatch.setattr(scraper, "_perform_http_request", fake_request)

    headers = scraper._build_authenticated_headers()

    assert headers["Authorization"] == scraper._bearer_token
    assert headers["x-guest-token"] == "TOKEN123"
    assert headers["x-twitter-active-user"] == "yes"
    assert activation_calls == [("https://api.x.com/1.1/guest/activate.json", "POST")]


def test_retry_fetch_json_recovers_after_rate_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    """Retry helper should back off and eventually parse a successful payload."""

    scraper = TwitterUnifiedScraper()
    scraper._has_auth_cookies = False

    monkeypatch.setattr(
        "app.scraping.twitter_unified.random.uniform",
        lambda _a, _b: 0.0,
    )

    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "app.scraping.twitter_unified.time.sleep",
        lambda duration: sleep_calls.append(duration),
    )

    call_sequence = iter(
        [
            (429, "application/json", '{"errors":[{"message":"rate limit"}]}'),
            (429, "application/json", '{"errors":[{"message":"rate limit"}]}'),
            (200, "application/json", '{"data":{"ok":true}}'),
        ]
    )

    def fake_headers() -> dict[str, str]:
        return {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json, text/plain, */*",
            "Authorization": scraper._bearer_token,
            "x-guest-token": "TOKEN123",
            "x-twitter-active-user": "yes",
        }

    monkeypatch.setattr(scraper, "_build_authenticated_headers", fake_headers)

    tokens_seen: list[str | None] = []

    def fake_request(url: str, method: str, headers: dict[str, str], data: bytes | None) -> tuple[int, str, str]:
        tokens_seen.append(headers.get("x-guest-token"))
        return next(call_sequence)

    monkeypatch.setattr(scraper, "_perform_http_request", fake_request)

    response = DummyResponse(
        url="https://api.x.com/1.1/graphql/user_flow.json",
        status=429,
        content_type="application/json",
        payload=b"",
        request=DummyRequest(
            url="https://api.x.com/1.1/graphql/user_flow.json",
            method="GET",
        ),
    )

    decoded, meta = scraper._retry_fetch_json(response, response.status)

    assert decoded is not None
    data, length = decoded
    assert data == {"data": {"ok": True}}
    assert length == len('{"data":{"ok":true}}')
    assert sleep_calls == [0.5, 1.0]
    assert tokens_seen == ["TOKEN123", "TOKEN123", "TOKEN123"]
    assert meta["token_refreshed"] is False


def test_retry_fetch_json_refreshes_guest_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """401 responses should trigger guest token refresh and retry."""

    scraper = TwitterUnifiedScraper()
    scraper._has_auth_cookies = False
    scraper._guest_token = "TOKEN_OLD"

    monkeypatch.setattr(
        "app.scraping.twitter_unified.random.uniform",
        lambda _a, _b: 0.0,
    )

    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "app.scraping.twitter_unified.time.sleep",
        lambda duration: sleep_calls.append(duration),
    )

    def fake_ensure_guest_token(force_refresh: bool = False) -> str | None:
        if force_refresh:
            scraper._guest_token = "TOKEN_REFRESHED"
        elif scraper._guest_token is None:
            scraper._guest_token = "TOKEN_INITIAL"
        return scraper._guest_token

    monkeypatch.setattr(scraper, "_ensure_guest_token", fake_ensure_guest_token)

    def real_headers() -> dict[str, str]:
        headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json, text/plain, */*",
        }
        token = scraper._guest_token
        if token:
            headers["Authorization"] = scraper._bearer_token
            headers["x-guest-token"] = token
            headers["x-twitter-active-user"] = "yes"
        return headers

    monkeypatch.setattr(scraper, "_build_authenticated_headers", real_headers)

    call_sequence = iter(
        [
            (401, "application/json", '{"errors":[{"message":"invalid"}]}'),
            (200, "application/json", '{"data":{"ok":true}}'),
        ]
    )

    tokens_seen: list[str | None] = []

    def fake_request(url: str, method: str, headers: dict[str, str], data: bytes | None) -> tuple[int, str, str]:
        tokens_seen.append(headers.get("x-guest-token"))
        return next(call_sequence)

    monkeypatch.setattr(scraper, "_perform_http_request", fake_request)

    response = DummyResponse(
        url="https://api.x.com/1.1/graphql/user_flow.json",
        status=401,
        content_type="application/json",
        payload=b"",
        request=DummyRequest(
            url="https://api.x.com/1.1/graphql/user_flow.json",
            method="GET",
        ),
    )

    decoded, meta = scraper._retry_fetch_json(response, response.status)

    assert decoded is not None
    data, length = decoded
    assert data == {"data": {"ok": True}}
    assert length == len('{"data":{"ok":true}}')
    assert sleep_calls == [0.5]
    assert tokens_seen == ["TOKEN_OLD", "TOKEN_REFRESHED"]
    assert meta["token_refreshed"] is True
