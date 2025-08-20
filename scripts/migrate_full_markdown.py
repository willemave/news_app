#!/usr/bin/env python3
"""
Migration script to consolidate full_markdown into StructuredSummary.
Moves full_markdown from metadata root level into summary.full_markdown.
"""

import json
import sys
from pathlib import Path

# Add the parent directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.core.settings import get_settings
from app.models.schema import Content

settings = get_settings()
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def migrate_full_markdown():
    """Migrate full_markdown from metadata root to summary.full_markdown."""
    db = SessionLocal()
    try:
        # Get all contents with metadata
        contents = db.query(Content).all()
        
        migrated_count = 0
        skipped_count = 0
        error_count = 0
        
        for content in contents:
            try:
                if not content.content_metadata:
                    skipped_count += 1
                    continue
                
                metadata = content.content_metadata
                needs_update = False
                
                # Check if we have a summary
                if "summary" in metadata and isinstance(metadata["summary"], dict):
                    summary = metadata["summary"]
                    
                    # Check if full_markdown is empty or missing in summary
                    if not summary.get("full_markdown"):
                        # Look for full_markdown in various places
                        full_markdown = None
                        
                        # 1. Check metadata root level
                        if metadata.get("full_markdown"):
                            full_markdown = metadata["full_markdown"]
                            # Remove from root level
                            del metadata["full_markdown"]
                        # 2. Check article_text field
                        elif metadata.get("article_text"):
                            full_markdown = metadata["article_text"]
                        # 3. Check content field
                        elif metadata.get("content"):
                            full_markdown = metadata["content"]
                        
                        # Update summary with full_markdown if we found content
                        if full_markdown:
                            # Create a new metadata dictionary to ensure SQLAlchemy detects the change
                            new_metadata = dict(metadata)
                            new_metadata["summary"]["full_markdown"] = full_markdown
                            content.content_metadata = new_metadata
                            # Also flag the field as modified to be extra sure
                            flag_modified(content, "content_metadata")
                            needs_update = True
                            print(f"Migrating content {content.id}: found full_markdown (length: {len(full_markdown)})")
                        else:
                            print(f"Content {content.id}: No full_markdown to migrate")
                    else:
                        # Check if there's a duplicate at root level to remove
                        if "full_markdown" in metadata:
                            # Create new metadata dict without the root full_markdown
                            new_metadata = dict(metadata)
                            del new_metadata["full_markdown"]
                            content.content_metadata = new_metadata
                            flag_modified(content, "content_metadata")
                            needs_update = True
                            print(f"Content {content.id}: Removing duplicate full_markdown from root")
                
                # Save updates if needed
                if needs_update:
                    db.commit()
                    migrated_count += 1
                else:
                    skipped_count += 1
                    
            except Exception as e:
                print(f"Error processing content {content.id}: {e}")
                error_count += 1
                db.rollback()
        
        print(f"\nMigration complete:")
        print(f"  Migrated: {migrated_count}")
        print(f"  Skipped: {skipped_count}")
        print(f"  Errors: {error_count}")
        
    finally:
        db.close()


if __name__ == "__main__":
    print("Starting full_markdown migration...")
    migrate_full_markdown()
    print("Done!")