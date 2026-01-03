"""Converters between domain models and database models."""

from datetime import datetime

from app.core.logging import get_logger
from app.models.metadata import ContentData, ContentStatus, ContentType
from app.models.schema import Content as DBContent

logger = get_logger(__name__)


def content_to_domain(db_content: DBContent) -> ContentData:
    """Convert database Content to domain ContentData."""
    try:
        metadata = dict(db_content.content_metadata or {})

        if db_content.platform and metadata.get("platform") is None:
            metadata["platform"] = db_content.platform
        if db_content.source and metadata.get("source") is None:
            metadata["source"] = db_content.source

        return ContentData(
            id=db_content.id,
            content_type=ContentType(db_content.content_type),
            url=db_content.url,
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
