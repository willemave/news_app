"""Converters between domain models and database models."""

from datetime import datetime

from app.models.metadata import ContentData, ContentStatus, ContentType
from app.models.schema import Content as DBContent


def content_to_domain(db_content: DBContent) -> ContentData:
    """Convert database Content to domain ContentData."""
    try:
        return ContentData(
            id=db_content.id,
            content_type=ContentType(db_content.content_type),
            url=db_content.url,
            title=db_content.title,
            status=ContentStatus(db_content.status),
            metadata=db_content.content_metadata or {},
            error_message=db_content.error_message,
            retry_count=db_content.retry_count or 0,
            created_at=db_content.created_at,
            processed_at=db_content.processed_at,
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
        existing.content_metadata = dumped_data["metadata"]
        existing.error_message = content_data.error_message
        existing.retry_count = content_data.retry_count
        if content_data.processed_at:
            existing.processed_at = content_data.processed_at
        existing.updated_at = datetime.utcnow()
        return existing
    else:
        # Create new
        return DBContent(
            content_type=content_data.content_type.value,
            url=str(content_data.url),
            title=content_data.title,
            status=content_data.status.value,
            content_metadata=content_data.model_dump(mode="json")["metadata"],
            error_message=content_data.error_message,
            retry_count=content_data.retry_count,
            created_at=content_data.created_at or datetime.utcnow(),
            processed_at=content_data.processed_at,
        )
