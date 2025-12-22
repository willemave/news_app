"""RSS/Atom feed detection service.

Detects RSS/Atom feed links in HTML and uses LLM to classify the feed type.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from urllib.parse import urlparse

from openai import APIConnectionError, APIError, OpenAI, RateLimitError
from pydantic import BaseModel, Field

from app.constants import SELF_SUBMISSION_SOURCE
from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)

# Configuration
FEED_CLASSIFICATION_MODEL = "gpt-4o-mini"
FEED_CLASSIFICATION_TIMEOUT = 10.0


class FeedClassificationResult(BaseModel):
    """Structured output schema for feed type classification."""

    feed_type: Literal["substack", "podcast_rss", "atom"] = Field(
        ...,
        description=(
            "Type of feed: 'substack' for Substack newsletters (including custom domains), "
            "'podcast_rss' for podcast feeds with audio episodes, "
            "'atom' for generic blog/news RSS feeds"
        ),
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for the classification (0.0-1.0)",
    )
    reasoning: str = Field(
        default="",
        description="Brief explanation for the classification decision",
    )


def extract_feed_links(html_content: str, page_url: str) -> list[dict[str, str]]:
    """Extract RSS/Atom feed links from HTML content.

    Args:
        html_content: Raw HTML content
        page_url: URL of the page (for resolving relative URLs)

    Returns:
        List of dicts with feed_url, feed_format, and title
    """
    feeds: list[dict[str, str]] = []

    # Pattern to match <link rel="alternate" type="application/rss+xml|atom+xml">
    link_pattern = re.compile(
        r"<link[^>]+rel=[\"']alternate[\"'][^>]*>",
        re.IGNORECASE | re.DOTALL,
    )

    for match in link_pattern.finditer(html_content):
        link_tag = match.group(0)

        # Extract type - must be RSS or Atom
        type_match = re.search(
            r"type=[\"']application/(rss\+xml|atom\+xml)[\"']",
            link_tag,
            re.IGNORECASE,
        )
        if not type_match:
            continue

        feed_format = "rss" if "rss" in type_match.group(1).lower() else "atom"

        # Extract href
        href_match = re.search(r"href=[\"']([^\"']+)[\"']", link_tag, re.IGNORECASE)
        if not href_match:
            continue

        feed_url = href_match.group(1)

        # Resolve relative URLs
        if not feed_url.startswith(("http://", "https://")):
            parsed_page = urlparse(page_url)
            if feed_url.startswith("/"):
                feed_url = f"{parsed_page.scheme}://{parsed_page.netloc}{feed_url}"
            else:
                base_path = parsed_page.path.rsplit("/", 1)[0]
                feed_url = f"{parsed_page.scheme}://{parsed_page.netloc}{base_path}/{feed_url}"

        # Extract title
        title_match = re.search(r"title=[\"']([^\"']*)[\"']", link_tag, re.IGNORECASE)
        title = title_match.group(1) if title_match else None

        feeds.append(
            {
                "feed_url": feed_url,
                "feed_format": feed_format,
                "title": title,
            }
        )

    return feeds


def classify_feed_type_with_llm(
    feed_url: str,
    page_url: str,
    page_title: str | None,
) -> FeedClassificationResult | None:
    """Use LLM to classify the feed type.

    Args:
        feed_url: The RSS/Atom feed URL
        page_url: The original page URL where the feed was found
        page_title: Title of the page (if available)

    Returns:
        FeedClassificationResult on success, None on failure
    """
    settings = get_settings()
    if not settings.openai_api_key:
        logger.warning(
            "OpenAI API key not configured, skipping feed classification",
            extra={
                "component": "feed_detection",
                "operation": "classify_feed_type",
            },
        )
        return None

    try:
        client = OpenAI(
            api_key=settings.openai_api_key,
            timeout=FEED_CLASSIFICATION_TIMEOUT,
        )

        prompt = _build_classification_prompt(feed_url, page_url, page_title)
        schema = FeedClassificationResult.model_json_schema()

        response = client.chat.completions.create(
            model=FEED_CLASSIFICATION_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "feed_classification",
                    "schema": schema,
                    "strict": True,
                },
            },
            max_tokens=256,
        )

        output_text = response.choices[0].message.content
        if not output_text:
            logger.warning(
                "No output from feed classification",
                extra={
                    "component": "feed_detection",
                    "operation": "classify_feed_type",
                    "context_data": {"feed_url": feed_url, "page_url": page_url},
                },
            )
            return None

        result = FeedClassificationResult.model_validate_json(output_text)

        logger.info(
            "Feed classified: type=%s, confidence=%.2f",
            result.feed_type,
            result.confidence,
            extra={
                "component": "feed_detection",
                "operation": "classify_feed_type",
                "context_data": {
                    "feed_url": feed_url,
                    "page_url": page_url,
                    "feed_type": result.feed_type,
                    "confidence": result.confidence,
                },
            },
        )
        return result

    except (RateLimitError, APIConnectionError, APIError) as e:
        logger.warning(
            "API error during feed classification: %s",
            e,
            extra={
                "component": "feed_detection",
                "operation": "classify_feed_type",
                "context_data": {"feed_url": feed_url, "error": str(e)},
            },
        )
        return None

    except Exception as e:
        logger.exception(
            "Unexpected error during feed classification: %s",
            e,
            extra={
                "component": "feed_detection",
                "operation": "classify_feed_type",
                "context_data": {"feed_url": feed_url, "error": str(e)},
            },
        )
        return None


def _build_classification_prompt(
    feed_url: str,
    page_url: str,
    page_title: str | None,
) -> str:
    """Build the classification prompt for the LLM."""
    title_line = f"Page Title: {page_title}\n" if page_title else ""

    return f"""Classify this RSS/Atom feed based on the feed URL and the page it was found on.

Feed URL: {feed_url}
Page URL: {page_url}
{title_line}
Classify as one of:
- "substack": Substack newsletter. Substack publications may use custom domains
  (e.g., chinatalk.media, stratechery.com) but are still Substack-powered.
  Look for substack.com in the feed URL, or indicators that this is a newsletter.
- "podcast_rss": Podcast feed with audio episodes. Look for podcast hosting platforms
  (anchor.fm, transistor.fm, libsyn, buzzsprout, simplecast, captivate, podbean, spreaker)
  or keywords like podcast/episode in the URL.
- "atom": Generic blog or news RSS feed that doesn't fit the above categories.

Return your classification with confidence score and brief reasoning."""


def detect_feeds_from_html(
    html_content: str,
    page_url: str,
    page_title: str | None = None,
    source: str | None = None,
) -> dict[str, Any] | None:
    """Detect feeds from HTML and return metadata for storage.

    Only processes user-submitted articles.

    Args:
        html_content: Raw HTML content
        page_url: URL of the page
        page_title: Title of the page (if available)
        source: Content source (e.g., "self submission")

    Returns:
        Dict with detected_feed info, or None if no feed found or not applicable
    """
    # Only process for user-submitted content
    if source != SELF_SUBMISSION_SOURCE:
        return None

    feeds = extract_feed_links(html_content, page_url)

    if not feeds:
        return None

    # Use the first detected feed (typically the main site feed)
    primary_feed = feeds[0]

    # Classify the feed type with LLM
    classification = classify_feed_type_with_llm(
        feed_url=primary_feed["feed_url"],
        page_url=page_url,
        page_title=page_title,
    )

    # Default to "atom" if LLM classification fails
    feed_type = classification.feed_type if classification else "atom"

    return {
        "detected_feed": {
            "url": primary_feed["feed_url"],
            "type": feed_type,
            "title": primary_feed.get("title"),
            "format": primary_feed["feed_format"],
        },
        "all_detected_feeds": feeds if len(feeds) > 1 else None,
    }
