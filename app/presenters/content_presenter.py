"""Presenters for content API responses."""

from typing import Any

from app.constants import SELF_SUBMISSION_SOURCE
from app.domain.converters import content_to_domain
from app.models.metadata import ContentData, ContentType
from app.models.schema import Content
from app.routers.api.models import ContentDetailResponse, ContentSummaryResponse, DetectedFeed
from app.utils.image_urls import (
    build_content_image_url,
    build_news_thumbnail_url,
    build_thumbnail_url,
)


def resolve_image_urls(domain_content: ContentData) -> tuple[str | None, str | None]:
    """Resolve image URLs without filesystem checks."""
    metadata = domain_content.metadata or {}

    if domain_content.content_type == ContentType.PODCAST:
        thumbnail = metadata.get("thumbnail_url")
        if thumbnail:
            return thumbnail, None

    image_url = metadata.get("image_url")
    thumbnail_url = metadata.get("thumbnail_url")
    has_generated_image = bool(metadata.get("image_generated_at"))

    if not image_url and has_generated_image and domain_content.id:
        if domain_content.content_type == ContentType.NEWS:
            image_url = build_news_thumbnail_url(domain_content.id)
        else:
            image_url = build_content_image_url(domain_content.id)

    if not thumbnail_url and has_generated_image and domain_content.id:
        thumbnail_url = build_thumbnail_url(domain_content.id)

    return image_url, thumbnail_url


def _extract_news_summary(domain_content: ContentData) -> dict[str, Any]:
    metadata = domain_content.metadata or {}
    article_meta = metadata.get("article", {})
    aggregator_meta = metadata.get("aggregator", {})
    summary_meta = metadata.get("summary", {})

    key_points = summary_meta.get("bullet_points") or summary_meta.get("key_points")
    news_key_points = None
    if key_points:
        news_key_points = [
            point.get("text") if isinstance(point, dict) else point for point in key_points
        ]

    return {
        "news_article_url": article_meta.get("url"),
        "news_discussion_url": aggregator_meta.get("url"),
        "news_key_points": news_key_points,
        "news_summary_text": domain_content.summary,
        "item_count": len(domain_content.news_items) if domain_content.news_items else None,
        "is_aggregate": domain_content.is_aggregate,
        "classification": summary_meta.get("classification"),
    }


def is_ready_for_list(domain_content: ContentData, image_url: str | None) -> bool:
    """Return True when content has enough data to appear in list views."""
    if domain_content.content_type != ContentType.ARTICLE:
        return True
    if not domain_content.bullet_points:
        return False
    return bool(image_url)


def build_content_summary_response(
    content: Content,
    domain_content: ContentData,
    is_read: bool,
    is_favorited: bool,
    image_url: str | None = None,
    thumbnail_url: str | None = None,
) -> ContentSummaryResponse:
    """Build a summary response for list/search views."""
    if image_url is None or thumbnail_url is None:
        image_url, thumbnail_url = resolve_image_urls(domain_content)

    classification = None
    if domain_content.structured_summary:
        classification = domain_content.structured_summary.get("classification")

    news_article_url = None
    news_discussion_url = None
    news_key_points = None
    news_summary_text = domain_content.short_summary
    item_count = None
    is_aggregate = domain_content.is_aggregate

    if domain_content.content_type == ContentType.NEWS:
        news_fields = _extract_news_summary(domain_content)
        news_article_url = news_fields["news_article_url"]
        news_discussion_url = news_fields["news_discussion_url"]
        news_key_points = news_fields["news_key_points"]
        news_summary_text = news_fields["news_summary_text"]
        item_count = news_fields["item_count"]
        is_aggregate = news_fields["is_aggregate"]
        classification = news_fields["classification"] or classification

    return ContentSummaryResponse(
        id=domain_content.id,
        content_type=domain_content.content_type.value,
        url=str(domain_content.url),
        title=domain_content.display_title,
        source=domain_content.source,
        platform=domain_content.platform or content.platform,
        status=domain_content.status.value,
        short_summary=news_summary_text,
        created_at=domain_content.created_at.isoformat() if domain_content.created_at else "",
        processed_at=(
            domain_content.processed_at.isoformat() if domain_content.processed_at else None
        ),
        classification=classification,
        publication_date=domain_content.publication_date.isoformat()
        if domain_content.publication_date
        else None,
        is_read=is_read,
        is_favorited=is_favorited,
        is_aggregate=is_aggregate,
        item_count=item_count,
        news_article_url=news_article_url,
        news_discussion_url=news_discussion_url,
        news_key_points=news_key_points,
        news_summary=news_summary_text,
        user_status="inbox"
        if domain_content.content_type in (ContentType.ARTICLE, ContentType.PODCAST)
        else None,
        image_url=image_url,
        thumbnail_url=thumbnail_url,
    )


def build_content_detail_response(
    content: Content,
    domain_content: ContentData,
    is_read: bool,
    is_favorited: bool,
    detected_feed_data: dict[str, Any] | None,
    can_subscribe: bool,
) -> ContentDetailResponse:
    """Build a detail response for content."""
    image_url, thumbnail_url = resolve_image_urls(domain_content)

    structured_summary = domain_content.structured_summary
    bullet_points = domain_content.bullet_points
    quotes = domain_content.quotes
    topics = domain_content.topics
    full_markdown = domain_content.full_markdown
    rendered_markdown = domain_content.rendered_news_markdown
    news_items = domain_content.news_items
    news_article_url = None
    news_discussion_url = None
    news_key_points = None
    news_summary_text = domain_content.summary

    if domain_content.content_type == ContentType.NEWS:
        news_fields = _extract_news_summary(domain_content)
        news_article_url = news_fields["news_article_url"]
        news_discussion_url = news_fields["news_discussion_url"]
        news_key_points = news_fields["news_key_points"]
        news_summary_text = news_fields["news_summary_text"]
        structured_summary = None
        bullet_points = []
        quotes = []
        topics = []
        full_markdown = None
        rendered_markdown = None
        news_items = []

    detected_feed = None
    if detected_feed_data:
        detected_feed = DetectedFeed(
            url=detected_feed_data["url"],
            type=detected_feed_data["type"],
            title=detected_feed_data.get("title"),
            format=detected_feed_data.get("format", "rss"),
        )

    return ContentDetailResponse(
        id=domain_content.id,
        content_type=domain_content.content_type.value,
        url=str(domain_content.url),
        title=domain_content.title,
        display_title=domain_content.display_title,
        source=domain_content.source,
        status=domain_content.status.value,
        error_message=domain_content.error_message,
        retry_count=domain_content.retry_count,
        metadata=domain_content.metadata,
        created_at=domain_content.created_at.isoformat() if domain_content.created_at else "",
        updated_at=content.updated_at.isoformat() if content.updated_at else None,
        processed_at=domain_content.processed_at.isoformat()
        if domain_content.processed_at
        else None,
        checked_out_by=content.checked_out_by,
        checked_out_at=content.checked_out_at.isoformat() if content.checked_out_at else None,
        publication_date=domain_content.publication_date.isoformat()
        if domain_content.publication_date
        else None,
        is_read=is_read,
        is_favorited=is_favorited,
        summary=news_summary_text,
        short_summary=news_summary_text,
        structured_summary=structured_summary,
        bullet_points=bullet_points,
        quotes=quotes,
        topics=topics,
        full_markdown=full_markdown,
        is_aggregate=domain_content.is_aggregate,
        rendered_markdown=rendered_markdown,
        news_items=news_items,
        news_article_url=news_article_url,
        news_discussion_url=news_discussion_url,
        news_key_points=news_key_points,
        news_summary=news_summary_text,
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        detected_feed=detected_feed,
        can_subscribe=can_subscribe,
    )


def build_domain_content(content: Content) -> ContentData:
    """Convert DB content to domain content."""
    return content_to_domain(content)


def can_subscribe_for_feed(
    domain_content: ContentData,
    detected_feed_data: dict[str, Any] | None,
) -> bool:
    """Check if user can subscribe to a detected feed."""
    if not detected_feed_data:
        return False
    return (
        domain_content.content_type == ContentType.NEWS
        or domain_content.source == SELF_SUBMISSION_SOURCE
    )
