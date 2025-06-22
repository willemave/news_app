#!/usr/bin/env python3
"""
Reset content processing in the database.
This script:
1. Clears all existing processing tasks
2. Resets content status to 'new' and clears metadata
3. Creates pending processing tasks for all content
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.settings import get_settings
from app.models.schema import Content, ProcessingTask, ContentStatus


def reset_content_processing():
    """Reset all content for re-processing."""
    # Get database settings
    settings = get_settings()
    
    # Create engine and session
    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    
    with SessionLocal() as db:
        try:
            # 1. Delete all existing processing tasks
            deleted_tasks = db.query(ProcessingTask).delete()
            print(f"Deleted {deleted_tasks} existing processing tasks")
            
            # 2. Reset all content status to 'new' and clear processing data
            reset_count = (
                db.query(Content)
                .update({
                    Content.status: ContentStatus.NEW.value,
                    Content.error_message: None,
                    Content.retry_count: 0,
                    Content.checked_out_by: None,
                    Content.checked_out_at: None,
                    Content.processed_at: None,
                    Content.content_metadata: {}  # Clear metadata
                })
            )
            print(f"Reset {reset_count} content items to 'new' status and cleared metadata")
            
            # 3. Create pending processing tasks for all content
            all_content = db.query(Content).all()
            
            for content in all_content:
                task = ProcessingTask(
                    task_type="process_content",
                    content_id=content.id,
                    status="pending",
                    payload={
                        "content_type": content.content_type,
                        "url": content.url,
                        "source": content.source
                    }
                )
                db.add(task)
            
            # Commit all changes
            db.commit()
            print(f"Created {len(all_content)} new processing tasks")
            print("\nReset complete! You can now run 'python run_workers.py' to re-process all content.")
            
        except Exception as e:
            db.rollback()
            print(f"Error: {e}")
            raise


if __name__ == "__main__":
    reset_content_processing()