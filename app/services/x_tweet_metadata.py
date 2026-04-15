"""Helpers for reusing stored X tweet metadata before calling the X API again."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from app.services.x_api import XTweet, build_tweet_processing_text


@dataclass(frozen=True)
class HydratedTweet:
    """Tweet reconstructed from previously persisted metadata."""

    tweet: XTweet
    source: str


def parse_x_created_at(value: str | None) -> datetime | None:
    """Parse X API timestamps into timezone-aware datetimes."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def coerce_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned or None


def coerce_optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def coerce_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _tweet_from_snapshot(
    snapshot: object,
    *,
    expected_tweet_id: str | None,
) -> XTweet | None:
    if not isinstance(snapshot, dict):
        return None
    snapshot_id = coerce_optional_string(snapshot.get("id")) or expected_tweet_id
    if snapshot_id is None:
        return None
    if expected_tweet_id is not None and snapshot_id != expected_tweet_id:
        return None
    text = coerce_optional_string(snapshot.get("text"))
    if text is None:
        return None
    return XTweet(
        id=snapshot_id,
        text=text,
        author_id=coerce_optional_string(snapshot.get("author_id")),
        author_username=coerce_optional_string(snapshot.get("author_username")),
        author_name=coerce_optional_string(snapshot.get("author_name")),
        created_at=coerce_optional_string(snapshot.get("created_at")),
        like_count=coerce_optional_int(snapshot.get("like_count")),
        retweet_count=coerce_optional_int(snapshot.get("retweet_count")),
        reply_count=coerce_optional_int(snapshot.get("reply_count")),
        conversation_id=coerce_optional_string(snapshot.get("conversation_id")),
        in_reply_to_user_id=coerce_optional_string(snapshot.get("in_reply_to_user_id")),
        referenced_tweet_types=coerce_string_list(snapshot.get("referenced_tweet_types")),
        article_title=coerce_optional_string(snapshot.get("article_title")),
        article_text=coerce_optional_string(snapshot.get("article_text")),
        note_tweet_text=coerce_optional_string(snapshot.get("note_tweet_text")),
        external_urls=coerce_string_list(snapshot.get("external_urls")),
        linked_tweet_ids=coerce_string_list(snapshot.get("linked_tweet_ids")),
    )


def hydrate_tweet_from_metadata(
    metadata: dict[str, Any] | None,
    *,
    tweet_id: str | None,
) -> HydratedTweet | None:
    """Reconstruct one tweet from stored metadata."""
    if not isinstance(metadata, dict):
        return None

    snapshot_tweet = _tweet_from_snapshot(
        metadata.get("tweet_snapshot"),
        expected_tweet_id=tweet_id,
    )
    if snapshot_tweet is not None:
        snapshot_source = coerce_optional_string(metadata.get("tweet_snapshot_source"))
        normalized_source = {
            "x_bookmarks_sync": "bookmark_sync_snapshot",
            "x_timeline_sync": "tweet_snapshot",
        }.get(snapshot_source or "", snapshot_source or "tweet_snapshot")
        return HydratedTweet(tweet=snapshot_tweet, source=normalized_source)

    metadata_tweet_id = coerce_optional_string(metadata.get("tweet_id")) or tweet_id
    if metadata_tweet_id is None:
        return None
    if tweet_id is not None and metadata_tweet_id != tweet_id:
        return None

    text = (
        coerce_optional_string(metadata.get("tweet_text"))
        or coerce_optional_string(metadata.get("tweet_note_tweet_text"))
        or coerce_optional_string(metadata.get("tweet_article_title"))
        or coerce_optional_string(metadata.get("tweet_article_text"))
    )
    if text is None:
        return None

    tweet = XTweet(
        id=metadata_tweet_id,
        text=text,
        author_id=None,
        author_username=coerce_optional_string(metadata.get("tweet_author_username")),
        author_name=coerce_optional_string(metadata.get("tweet_author")),
        created_at=coerce_optional_string(metadata.get("tweet_created_at")),
        like_count=coerce_optional_int(metadata.get("tweet_like_count")),
        retweet_count=coerce_optional_int(metadata.get("tweet_retweet_count")),
        reply_count=coerce_optional_int(metadata.get("tweet_reply_count")),
        conversation_id=None,
        in_reply_to_user_id=None,
        referenced_tweet_types=[],
        article_title=coerce_optional_string(metadata.get("tweet_article_title")),
        article_text=coerce_optional_string(metadata.get("tweet_article_text")),
        note_tweet_text=coerce_optional_string(metadata.get("tweet_note_tweet_text")),
        external_urls=coerce_string_list(metadata.get("tweet_external_urls")),
        linked_tweet_ids=coerce_string_list(metadata.get("tweet_linked_tweet_ids")),
    )
    return HydratedTweet(tweet=tweet, source="content_metadata")


def hydrate_included_tweets_from_metadata(metadata: dict[str, Any] | None) -> dict[str, XTweet]:
    """Reconstruct included referenced tweets persisted alongside a root tweet snapshot."""
    if not isinstance(metadata, dict):
        return {}
    raw_included = metadata.get("tweet_snapshot_included")
    if not isinstance(raw_included, dict):
        return {}

    hydrated: dict[str, XTweet] = {}
    for tweet_id, snapshot in raw_included.items():
        expected_id = tweet_id if isinstance(tweet_id, str) and tweet_id.strip() else None
        tweet = _tweet_from_snapshot(snapshot, expected_tweet_id=expected_id)
        if tweet is None:
            continue
        hydrated[tweet.id] = tweet
    return hydrated


def build_tweet_snapshot_metadata(
    *,
    tweet: XTweet,
    included_tweets: dict[str, XTweet] | None = None,
    snapshot_source: str,
) -> dict[str, Any]:
    """Build metadata payload for a root tweet plus any included referenced tweets."""
    metadata: dict[str, Any] = {
        "tweet_snapshot": asdict(tweet),
        "tweet_snapshot_source": snapshot_source,
    }
    if included_tweets:
        metadata["tweet_snapshot_included"] = {
            tweet_id: asdict(included_tweet) for tweet_id, included_tweet in included_tweets.items()
        }
    return metadata


def build_resolved_tweet_content(tweet: XTweet) -> tuple[str, str | None, datetime | None]:
    """Return text, author, and publication date for a hydrated tweet."""
    author = f"@{tweet.author_username}" if tweet.author_username else None
    publication_date = parse_x_created_at(tweet.created_at)
    return build_tweet_processing_text(tweet), author, publication_date
