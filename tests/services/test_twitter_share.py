"""Tests for Twitter share helpers."""

from __future__ import annotations

import httpx

from app.services import twitter_share


def test_tweet_url_helpers() -> None:
    assert twitter_share.extract_tweet_id("https://twitter.com/user/status/123") == "123"
    assert twitter_share.extract_tweet_id("https://x.com/i/status/456") == "456"
    assert (
        twitter_share.canonicalize_tweet_url("https://x.com/user/status/789")
        == "https://x.com/i/status/789"
    )
    assert twitter_share.is_tweet_url("https://example.com") is False


def test_fetch_tweet_detail_parses_thread(monkeypatch) -> None:
    tweet_result = {
        "rest_id": "123",
        "legacy": {
            "full_text": "Hello world",
            "created_at": "Wed Oct 05 20:17:27 +0000 2022",
            "conversation_id_str": "conv1",
            "favorite_count": 1,
            "retweet_count": 2,
            "reply_count": 3,
            "entities": {
                "urls": [
                    {"expanded_url": "https://example.com"},
                    {"expanded_url": "https://t.co/abc"},
                ]
            },
        },
        "core": {
            "user_results": {
                "result": {"legacy": {"screen_name": "alice", "name": "Alice"}}
            }
        },
    }
    thread_result = {
        "rest_id": "124",
        "legacy": {
            "full_text": "Second tweet",
            "created_at": "Wed Oct 05 20:18:27 +0000 2022",
            "conversation_id_str": "conv1",
            "favorite_count": 0,
            "retweet_count": 0,
            "reply_count": 0,
            "entities": {"urls": [{"expanded_url": "https://example.org"}]},
        },
        "core": {
            "user_results": {
                "result": {"legacy": {"screen_name": "alice", "name": "Alice"}}
            }
        },
    }
    payload = {
        "data": {
            "tweetResult": {"result": tweet_result},
            "threaded_conversation_with_injections_v2": {
                "instructions": [
                    {
                        "entries": [
                            {"content": {"itemContent": {"tweet_results": {"result": tweet_result}}}},
                            {"content": {"itemContent": {"tweet_results": {"result": thread_result}}}},
                        ]
                    }
                ]
            },
        }
    }

    class DummyClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, *args, **kwargs):
            return httpx.Response(200, json=payload)

        def post(self, *args, **kwargs):
            return httpx.Response(200, json=payload)

    monkeypatch.setattr(twitter_share, "_get_query_ids", lambda **kwargs: {"TweetDetail": "TEST"})
    monkeypatch.setattr(twitter_share.httpx, "Client", DummyClient)

    credentials = twitter_share.TwitterCredentials(
        auth_token="auth", ct0="ct0", user_agent="ua"
    )
    result = twitter_share.fetch_tweet_detail(
        twitter_share.TweetFetchParams(tweet_id="123", credentials=credentials)
    )

    assert result.success is True
    assert result.tweet is not None
    assert result.tweet.text == "Hello world"
    assert result.external_urls == ["https://example.com", "https://example.org"]
    assert [tweet.id for tweet in result.thread] == ["123", "124"]
