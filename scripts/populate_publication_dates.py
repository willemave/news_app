#!/usr/bin/env python3
"""Populate publication_date column from existing content_metadata."""

import sys
from pathlib import Path

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.settings import get_settings

settings = get_settings()
from app.core.logging import get_logger
from app.models.schema import Content

logger = get_logger(__name__)


def parse_date(date_value: Any) -> datetime | None:
    """Parse various date formats to datetime."""
    if not date_value:
        return None
    
    if isinstance(date_value, datetime):
        return date_value
    
    if isinstance(date_value, str):
        try:
            # Try ISO format first
            return datetime.fromisoformat(date_value.replace("Z", "+00:00"))
        except ValueError:
            try:
                # Try common date formats
                from dateutil import parser
                return parser.parse(date_value)
            except Exception:
                logger.warning(f"Could not parse date: {date_value}")
                return None
    
    return None


def populate_publication_dates() -> None:
    """Populate publication_date from content_metadata."""
    engine = create_engine(settings.database_url)
    
    with Session(engine) as session:
        # Get all content records
        stmt = select(Content).where(Content.publication_date.is_(None))
        contents = session.execute(stmt).scalars().all()
        
        print(f"Found {len(contents)} contents without publication_date")
        
        updated_count = 0
        skipped_count = 0
        
        for content in contents:
            if not content.content_metadata:
                skipped_count += 1
                continue
            
            # Look for publication_date in metadata
            pub_date = content.content_metadata.get("publication_date")
            if not pub_date:
                # Also check for common variations
                pub_date = (
                    content.content_metadata.get("publish_date") or
                    content.content_metadata.get("published_date") or
                    content.content_metadata.get("date")
                )
            
            if pub_date:
                parsed_date = parse_date(pub_date)
                if parsed_date:
                    content.publication_date = parsed_date
                    updated_count += 1
                    logger.info(f"Updated content {content.id} with publication date: {parsed_date}")
                else:
                    skipped_count += 1
            else:
                # If no publication date in metadata, use created_at as fallback
                content.publication_date = content.created_at
                updated_count += 1
                logger.info(f"Content {content.id}: Using created_at as publication_date fallback")
        
        session.commit()
        
        print(f"Population complete: Updated {updated_count} records, skipped {skipped_count}")


if __name__ == "__main__":
    print("Starting publication date population...")
    populate_publication_dates()
    print("Done!")