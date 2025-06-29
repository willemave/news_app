#!/usr/bin/env python3
"""Script to resummarize all podcast content."""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Activate virtual environment if it exists
venv_path = project_root / ".venv"
if venv_path.exists():
    activate_this = venv_path / "bin" / "activate_this.py"
    if activate_this.exists():
        exec(open(activate_this).read(), {'__file__': str(activate_this)})

from datetime import datetime

from sqlalchemy import and_

from app.core.db import get_db
from app.core.logging import get_logger, setup_logging
from app.models.schema import Content
from app.services.google_flash import GoogleFlashService

# Set up logging
setup_logging()
logger = get_logger(__name__)


def resummarize_podcasts(dry_run: bool = False, limit: int | None = None):
    """
    Resummarize all podcast content that has transcripts.
    
    Args:
        dry_run: If True, just show what would be processed without making changes
        limit: Maximum number of podcasts to process
    """
    print(f"Starting resummarize_podcasts with dry_run={dry_run}, limit={limit}")
    
    try:
        llm_service = GoogleFlashService()
        print("GoogleFlashService initialized")
    except Exception as e:
        print(f"Failed to initialize GoogleFlashService: {e}")
        return
    
    with get_db() as db:
        # Find all podcasts with transcripts
        # First get all podcasts
        query = db.query(Content).filter(Content.content_type == "podcast")
        
        if limit:
            query = query.limit(limit)
            
        podcasts = query.all()
        
        # Filter for those with transcripts
        podcasts_with_transcripts = []
        for podcast in podcasts:
            if podcast.content_metadata and podcast.content_metadata.get("transcript"):
                podcasts_with_transcripts.append(podcast)
        
        logger.info(f"Found {len(podcasts_with_transcripts)} podcasts with transcripts out of {len(podcasts)} total podcasts")
        
        podcasts = podcasts_with_transcripts
        
        if dry_run:
            logger.info("DRY RUN - No changes will be made")
        
        success_count = 0
        error_count = 0
        
        for i, podcast in enumerate(podcasts, 1):
            try:
                logger.info(f"[{i}/{len(podcasts)}] Processing: {podcast.title}")
                
                # Get transcript from metadata
                transcript = podcast.content_metadata.get("transcript", "")
                
                if not transcript:
                    logger.warning(f"No transcript found for podcast {podcast.id}")
                    continue
                
                if dry_run:
                    logger.info(f"Would resummarize podcast {podcast.id}: {podcast.title}")
                    continue
                
                # Generate new summary
                logger.info(f"Generating summary for podcast {podcast.id}")
                summary = llm_service.summarize_content_sync(transcript)
                
                if summary:
                    # Update content with new summary
                    metadata = dict(podcast.content_metadata or {})
                    if hasattr(summary, "model_dump"):
                        metadata["summary"] = summary.model_dump(mode="json")
                    else:
                        metadata["summary"] = summary
                    metadata["summarization_date"] = datetime.utcnow().isoformat()
                    metadata["resummarized"] = True
                    
                    # Assign new dictionary to trigger SQLAlchemy change detection
                    podcast.content_metadata = metadata
                    
                    # Update classification if available
                    if hasattr(summary, "classification") and summary.classification:
                        podcast.classification = summary.classification
                    
                    db.commit()
                    
                    logger.info(f"Successfully resummarized podcast {podcast.id}")
                    success_count += 1
                else:
                    logger.error(f"Failed to generate summary for podcast {podcast.id}")
                    error_count += 1
                    
            except Exception as e:
                logger.error(f"Error processing podcast {podcast.id}: {e}", exc_info=True)
                error_count += 1
                db.rollback()
        
        logger.info(f"\nSummary:")
        logger.info(f"Total podcasts: {len(podcasts)}")
        logger.info(f"Successfully resummarized: {success_count}")
        logger.info(f"Errors: {error_count}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Resummarize all podcast content")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without making changes"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of podcasts to process"
    )
    
    args = parser.parse_args()
    
    resummarize_podcasts(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()