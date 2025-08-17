#!/usr/bin/env python3
"""
Migration script to update existing content with platform field and standardized source format.

This script:
1. Adds platform field based on current source values
2. Updates source field to new "platform:source" format
3. Handles all known content types
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.schema import Base, Content

logger = get_logger(__name__)
settings = get_settings()


def migrate_content_platforms():
    """Migrate existing content to new platform/source format."""
    # Create database connection
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Get all content without platform field set
        contents = session.query(Content).filter(Content.platform.is_(None)).all()
        
        logger.info(f"Found {len(contents)} content items to migrate")
        
        migrated_count = 0
        error_count = 0
        
        for content in contents:
            try:
                metadata = content.content_metadata or {}
                current_source = content.source or metadata.get("source", "")
                
                # Determine platform and new source format based on patterns
                platform = None
                new_source = None
                
                if not current_source:
                    logger.warning(f"Content {content.id} has no source, skipping")
                    continue
                
                # Check if already in new format
                if ":" in current_source:
                    parts = current_source.split(":", 1)
                    platform = parts[0]
                    new_source = current_source
                
                # Reddit content
                elif any(sub in current_source for sub in ["MachineLearning", "artificial", "ArtificialInteligence", 
                                                            "ChatGPTPro", "reinforcementlearning", "mlscaling",
                                                            "NooTopics", "SquarePOS_Users", "POS", "front"]):
                    platform = "reddit"
                    new_source = f"reddit:{current_source}"
                
                # HackerNews content
                elif current_source.lower() in ["hackernews", "hacker news"]:
                    platform = "hackernews"
                    new_source = "hackernews:HackerNews"
                
                # Podcast content (check content_type)
                elif content.content_type == "podcast":
                    platform = "podcast"
                    new_source = f"podcast:{current_source}"
                
                # YouTube content (check URL or metadata)
                elif "youtube.com" in content.url or "youtu.be" in content.url:
                    platform = "youtube"
                    # Try to get channel from metadata
                    channel = metadata.get("channel", current_source)
                    new_source = f"youtube:{channel}"
                
                # Substack and other newsletter content
                else:
                    # Assume it's substack if not matching other patterns
                    platform = "substack"
                    new_source = f"substack:{current_source}"
                
                # Update content
                content.platform = platform
                content.source = new_source
                
                # Also update metadata
                if content.content_metadata:
                    content.content_metadata["platform"] = platform
                    content.content_metadata["source"] = new_source
                
                migrated_count += 1
                
                if migrated_count % 100 == 0:
                    logger.info(f"Migrated {migrated_count} items...")
                    session.commit()
                
            except Exception as e:
                logger.error(f"Error migrating content {content.id}: {e}")
                error_count += 1
                continue
        
        # Final commit
        session.commit()
        
        logger.info(f"Migration complete! Migrated: {migrated_count}, Errors: {error_count}")
        
        # Show summary of platforms
        platform_counts = session.query(
            Content.platform, 
            text("COUNT(*)")
        ).group_by(Content.platform).all()
        
        logger.info("Platform distribution:")
        for platform, count in platform_counts:
            logger.info(f"  {platform or 'None'}: {count}")
            
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logger.info("Starting platform data migration...")
    migrate_content_platforms()
    logger.info("Migration script completed")