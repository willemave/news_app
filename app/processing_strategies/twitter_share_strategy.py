"""Tweet-only processing strategy for share-sheet ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from app.core.logging import get_logger
from app.processing_strategies.base_strategy import UrlProcessorStrategy
from app.services.http import NonRetryableError
from app.services.twitter_share import (
    TweetFetchParams,
    extract_tweet_id,
    fetch_tweet_detail,
    resolve_twitter_credentials,
)

logger = get_logger(__name__)


@dataclass(frozen=True)
class TweetContent:
    """Parsed tweet content payload."""

    text: str
    author: str | None
    publication_date: datetime | None


def _parse_tweet_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%a %b %d %H:%M:%S %z %Y")
    except Exception:
        return None


def _build_thread_text(thread: list[str]) -> str:
    cleaned = [text.strip() for text in thread if isinstance(text, str) and text.strip()]
    return "\n\n".join(cleaned)


class TwitterShareProcessorStrategy(UrlProcessorStrategy):
    """Process tweet URLs by fetching text via Twitter GraphQL."""

    def can_handle_url(self, url: str, response_headers: httpx.Headers | None = None) -> bool:
        return extract_tweet_id(url) is not None

    def download_content(self, url: str) -> TweetContent:
        tweet_id = extract_tweet_id(url)
        if not tweet_id:
            raise NonRetryableError("Invalid tweet URL")

        credentials_result = resolve_twitter_credentials()
        if not credentials_result.success or not credentials_result.credentials:
            raise NonRetryableError(credentials_result.error or "Twitter credentials unavailable")

        fetch_result = fetch_tweet_detail(
            TweetFetchParams(
                tweet_id=tweet_id,
                credentials=credentials_result.credentials,
                include_thread=True,
            )
        )

        if not fetch_result.success or not fetch_result.tweet:
            raise NonRetryableError(fetch_result.error or "TweetDetail request failed")

        thread = fetch_result.thread or [fetch_result.tweet]
        thread_text = _build_thread_text([tweet.text for tweet in thread])
        if not thread_text:
            raise NonRetryableError("Tweet thread contained no text to summarize")

        author = None
        if fetch_result.tweet.author_username:
            author = f"@{fetch_result.tweet.author_username}"
        publication_date = _parse_tweet_date(fetch_result.tweet.created_at)

        return TweetContent(text=thread_text, author=author, publication_date=publication_date)

    def extract_data(self, content: TweetContent, url: str) -> dict[str, Any]:
        title = content.text.split("\n", 1)[0].strip() if content.text else "Tweet"

        return {
            "title": title[:280] if title else "Tweet",
            "author": content.author,
            "publication_date": content.publication_date,
            "text_content": content.text,
            "content_type": "text",
            "final_url_after_redirects": url,
        }

    def prepare_for_llm(self, extracted_data: dict[str, Any]) -> dict[str, Any]:
        text_content = (extracted_data.get("text_content") or "").strip()
        return {
            "content_to_filter": text_content,
            "content_to_summarize": text_content,
            "is_pdf": False,
        }
