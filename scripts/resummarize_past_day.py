#!/usr/bin/env python3
"""Script to resummarize content from the past day."""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Activate virtual environment if it exists
venv_path = project_root / ".venv"
if venv_path.exists():
    activate_this = venv_path / "bin" / "activate_this.py"
    if activate_this.exists():
        exec(open(activate_this).read(), {"__file__": str(activate_this)})

from sqlalchemy import and_, or_

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.models.metadata import ContentStatus
from app.models.schema import Content
from app.services.openai_llm import get_openai_summarization_service

# Set up logging
setup_logging()
logger = get_logger(__name__)


def resummarize_past_day_content(
    dry_run: bool = False,
    limit: int | None = None,
    days_back: int = 1,
    content_types: list[str] | None = None,
):
    """
    Resummarize content from the past day(s).

    Args:
        dry_run: If True, just show what would be processed without making changes
        limit: Maximum number of items to process
        days_back: Number of days to look back (default 1)
        content_types: List of content types to process (default all)
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days_back)
    
    print(f"Starting resummarize_past_day_content")
    print(f"  dry_run={dry_run}")
    print(f"  limit={limit}")
    print(f"  days_back={days_back}")
    print(f"  cutoff_date={cutoff_date.isoformat()}")
    print(f"  content_types={content_types or 'all'}")

    try:
        llm_service = get_openai_summarization_service()
        print("OpenAI summarization service initialized")
    except Exception as e:
        print(f"Failed to initialize OpenAI summarization service: {e}")
        return

    with get_db() as db:
        # Build query for content from the past day(s)
        query = db.query(Content).filter(
            and_(
                Content.created_at >= cutoff_date,
                Content.status == ContentStatus.COMPLETED.value,
            )
        )

        # Filter by content types if specified
        if content_types:
            query = query.filter(Content.content_type.in_(content_types))

        # Order by creation date (oldest first)
        query = query.order_by(Content.created_at)

        if limit:
            query = query.limit(limit)

        content_items = query.all()

        logger.info(f"Found {len(content_items)} content items from the past {days_back} day(s)")

        if dry_run:
            logger.info("DRY RUN - No changes will be made")
            logger.info("\nContent to be processed:")
            for item in content_items:
                logger.info(
                    f"  [{item.content_type}] {item.title} "
                    f"(created: {item.created_at.isoformat()})"
                )
            return

        success_count = 0
        error_count = 0
        skipped_count = 0

        for i, content in enumerate(content_items, 1):
            try:
                logger.info(
                    f"[{i}/{len(content_items)}] Processing {content.content_type}: {content.title}"
                )

                # Get content to summarize based on type
                text_to_summarize = None
                
                if content.content_type == "podcast":
                    # For podcasts, use transcript
                    text_to_summarize = content.content_metadata.get("transcript", "")
                    if not text_to_summarize:
                        logger.warning(f"No transcript found for podcast {content.id}")
                        skipped_count += 1
                        continue
                        
                elif content.content_type == "article":
                    # For articles, use content
                    text_to_summarize = content.content_metadata.get("content", "")
                    if not text_to_summarize:
                        logger.warning(f"No content found for article {content.id}")
                        skipped_count += 1
                        continue
                        
                else:
                    # For other types, try to use content or description
                    text_to_summarize = (
                        content.content_metadata.get("content") or
                        content.content_metadata.get("description") or
                        content.content_metadata.get("text", "")
                    )
                    if not text_to_summarize:
                        logger.warning(f"No summarizable content found for {content.content_type} {content.id}")
                        skipped_count += 1
                        continue

                # Generate new summary
                logger.info(f"Generating summary for {content.content_type} {content.id}")
                summary = llm_service.summarize_content(text_to_summarize)

                if summary:
                    # Update content with new summary
                    metadata = dict(content.content_metadata or {})
                    if hasattr(summary, "model_dump"):
                        metadata["summary"] = summary.model_dump(mode="json")
                    else:
                        metadata["summary"] = summary
                    metadata["summarization_date"] = datetime.utcnow().isoformat()
                    metadata["resummarized"] = True

                    # Assign new dictionary to trigger SQLAlchemy change detection
                    content.content_metadata = metadata

                    # Update classification if available
                    if hasattr(summary, "classification") and summary.classification:
                        content.classification = summary.classification

                    db.commit()

                    logger.info(f"Successfully resummarized {content.content_type} {content.id}")
                    success_count += 1
                else:
                    logger.error(f"Failed to generate summary for {content.content_type} {content.id}")
                    error_count += 1

            except Exception as e:
                logger.error(
                    f"Error processing {content.content_type} {content.id}: {e}",
                    exc_info=True
                )
                error_count += 1
                db.rollback()

        logger.info(f"\nSummary:")
        logger.info(f"Total content items: {len(content_items)}")
        logger.info(f"Successfully resummarized: {success_count}")
        logger.info(f"Skipped (no content): {skipped_count}")
        logger.info(f"Errors: {error_count}")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Resummarize content from the past day(s)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of items to process",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=1,
        help="Number of days to look back (default: 1)",
    )
    parser.add_argument(
        "--types",
        nargs="+",
        choices=["article", "podcast", "video"],
        help="Content types to process (default: all)",
    )

    args = parser.parse_args()

    resummarize_past_day_content(
        dry_run=args.dry_run,
        limit=args.limit,
        days_back=args.days_back,
        content_types=args.types,
    )


if __name__ == "__main__":
    main()