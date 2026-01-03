"""Converters between domain models and database models."""

from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.models.metadata import ContentData, ContentStatus, ContentType
from app.models.schema import Content as DBContent
from app.utils.url_utils import is_http_url

logger = get_logger(__name__)


def _select_http_url(raw_url: str, metadata: dict[str, Any], content_type: str) -> str:
    candidates: list[str | None] = [raw_url]

    if content_type == ContentType.NEWS.value:
        article = metadata.get("article")
        if isinstance(article, dict):
            candidates.insert(0, article.get("url"))

    candidates.extend(
        [
            metadata.get("final_url_after_redirects"),
            metadata.get("final_url"),
            metadata.get("url"),
        ]
    )

    for candidate in candidates:
        if isinstance(candidate, str) and is_http_url(candidate):
            return candidate

    return raw_url


def content_to_domain(db_content: DBContent) -> ContentData:
    """Convert database Content to domain ContentData."""
    try:
        metadata = dict(db_content.content_metadata or {})

        if db_content.platform and metadata.get("platform") is None:
            metadata["platform"] = db_content.platform
        if db_content.source and metadata.get("source") is None:
            metadata["source"] = db_content.source

        resolved_url = _select_http_url(
            db_content.url,
            metadata,
            db_content.content_type,
        )

        return ContentData(
            id=db_content.id,
            content_type=ContentType(db_content.content_type),
            url=resolved_url,
            source_url=db_content.source_url or db_content.url,
            title=db_content.title,
            status=ContentStatus(db_content.status),
            metadata=metadata,
            platform=db_content.platform,
            source=db_content.source,
            error_message=db_content.error_message,
            retry_count=db_content.retry_count or 0,
            created_at=db_content.created_at,
            processed_at=db_content.processed_at,
            publication_date=db_content.publication_date,
        )
    except Exception as e:
        logger.exception(
            "Error converting content %s: %s",
            db_content.id,
            e,
            extra={
                "component": "content_converter",
                "operation": "content_to_domain",
                "context_data": {
                    "content_id": db_content.id,
                    "metadata": db_content.content_metadata,
                },
            },
        )
        raise


def domain_to_content(content_data: ContentData, existing: DBContent | None = None) -> DBContent:
    """Convert domain ContentData to database Content."""
    if existing:
        # Update existing
        existing.title = content_data.title
        existing.status = content_data.status.value
        new_url = str(content_data.url)
        if new_url and new_url != existing.url:
            existing.url = new_url
        if content_data.source_url:
            existing.source_url = content_data.source_url
        elif existing.source_url is None:
            existing.source_url = new_url
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

        # Sync classification from summary metadata to DB column for filtering
        summary = md.get("summary")
        if isinstance(summary, dict):
            classification = summary.get("classification")
            if classification in ("to_read", "skip"):
                existing.classification = classification

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
            source_url=content_data.source_url or str(content_data.url),
            title=content_data.title,
            status=content_data.status.value,
            platform=(plat.strip().lower() if isinstance(plat, str) and plat.strip() else None),
            source=(src.strip() if isinstance(src, str) and src.strip() else None),
            content_metadata=md,
            error_message=content_data.error_message,
            retry_count=content_data.retry_count,
            created_at=content_data.created_at or datetime.utcnow(),
            processed_at=content_data.processed_at,
        )
