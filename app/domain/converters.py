"""Converters between domain models and database models."""

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.models.metadata import ContentData, ContentStatus, ContentType
from app.models.schema import Content as DBContent


def normalize_news_metadata(
    metadata: dict[str, Any] | None,
    fallback_url: str | None,
    fallback_title: str | None,
    fallback_source: str | None,
) -> dict[str, Any]:
    """Ensure news metadata includes the required ``article`` structure.

    Older scraper payloads (notably Reddit) emitted aggregator-style metadata without
    the mandatory ``article`` block expected by ``NewsMetadata``. This helper patches
    the payload before validation so workers can continue processing legacy rows.
    """

    raw_metadata: dict[str, Any] = dict(metadata or {})

    # Seed the article payload with any existing data without mutating the original.
    existing_article = raw_metadata.get("article")
    article: dict[str, Any] = dict(existing_article) if isinstance(existing_article, dict) else {}

    def _first_item_value(items: Any, key: str) -> Any:
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return first.get(key)
        return None

    def _coerce_str(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    # Determine canonical article URL. Prefer existing data, fall back to scraped URL.
    candidate_urls: list[str | None] = [
        _coerce_str(article.get("url")),
        _coerce_str(_first_item_value(raw_metadata.get("items"), "url")),
        _coerce_str(raw_metadata.get("article_url")),
        _coerce_str(raw_metadata.get("canonical_url")),
        _coerce_str(fallback_url),
    ]
    article_url = next((url for url in candidate_urls if url), None)
    if article_url:
        article["url"] = article_url

    # Populate title using existing metadata, first aggregated item, or DB record.
    candidate_titles: list[str | None] = [
        _coerce_str(article.get("title")),
        _coerce_str(raw_metadata.get("title")),
        _coerce_str(raw_metadata.get("headline")),
        _coerce_str(_first_item_value(raw_metadata.get("items"), "title")),
        _coerce_str(fallback_title),
    ]
    article_title = next((title for title in candidate_titles if title), None)
    if article_title:
        article["title"] = article_title

    # Infer source domain either from the URL or fallback source metadata.
    if not _coerce_str(article.get("source_domain")) and article.get("url"):
        try:
            domain = urlparse(str(article["url"]))
        except ValueError:
            domain = None
        else:
            host = domain.netloc
            if host:
                article["source_domain"] = host

    if not _coerce_str(article.get("source_domain")) and _coerce_str(fallback_source):
        article["source_domain"] = _coerce_str(fallback_source)

    # Strip empty values so downstream JSON dumps stay compact.
    cleaned_article = {
        key: value
        for key, value in article.items()
        if value not in (None, "", {})
    }

    raw_metadata["article"] = cleaned_article
    return raw_metadata


def content_to_domain(db_content: DBContent) -> ContentData:
    """Convert database Content to domain ContentData."""
    try:
        metadata = dict(db_content.content_metadata or {})

        if db_content.platform and metadata.get("platform") is None:
            metadata["platform"] = db_content.platform
        if db_content.source and metadata.get("source") is None:
            metadata["source"] = db_content.source

        if db_content.content_type == ContentType.NEWS.value:
            metadata = normalize_news_metadata(
                metadata,
                fallback_url=db_content.url,
                fallback_title=db_content.title,
                fallback_source=metadata.get("source") or db_content.source,
            )
        
        return ContentData(
            id=db_content.id,
            content_type=ContentType(db_content.content_type),
            url=db_content.url,
            title=db_content.title,
            status=ContentStatus(db_content.status),
            metadata=metadata,
            platform=db_content.platform,
            source=db_content.source,
            is_aggregate=bool(getattr(db_content, "is_aggregate", False)),
            error_message=db_content.error_message,
            retry_count=db_content.retry_count or 0,
            created_at=db_content.created_at,
            processed_at=db_content.processed_at,
            publication_date=db_content.publication_date,
        )
    except Exception as e:
        # Log the error with details
        print(f"Error converting content {db_content.id}: {e}")
        print(f"Metadata: {db_content.content_metadata}")
        raise


def domain_to_content(content_data: ContentData, existing: DBContent | None = None) -> DBContent:
    """Convert domain ContentData to database Content."""
    if existing:
        # Update existing
        existing.title = content_data.title
        existing.status = content_data.status.value
        # Serialize metadata to ensure datetime objects are handled
        dumped_data = content_data.model_dump(mode="json")
        md = dumped_data["metadata"] or {}
        # Keep DB columns for platform/source in sync with metadata if provided
        plat = md.get("platform")
        src = md.get("source")
        if isinstance(plat, str) and plat.strip():
            existing.platform = plat.strip().lower()
        if isinstance(src, str) and src.strip():
            existing.source = src.strip()
        existing.content_metadata = md
        if hasattr(existing, "is_aggregate"):
            existing.is_aggregate = content_data.is_aggregate
        existing.error_message = content_data.error_message
        existing.retry_count = content_data.retry_count
        if content_data.processed_at:
            existing.processed_at = content_data.processed_at
        existing.updated_at = datetime.utcnow()
        return existing
    else:
        # Create new
        dumped = content_data.model_dump(mode="json")
        md = dumped.get("metadata") or {}
        plat = md.get("platform")
        src = md.get("source")
        return DBContent(
            content_type=content_data.content_type.value,
            url=str(content_data.url),
            title=content_data.title,
            status=content_data.status.value,
            platform=(plat.strip().lower() if isinstance(plat, str) and plat.strip() else None),
            source=(src.strip() if isinstance(src, str) and src.strip() else None),
            content_metadata=md,
            is_aggregate=content_data.is_aggregate,
            error_message=content_data.error_message,
            retry_count=content_data.retry_count,
            created_at=content_data.created_at or datetime.utcnow(),
            processed_at=content_data.processed_at,
        )
