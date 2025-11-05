#!/usr/bin/env python3
"""Script to retranscribe all podcasts in the database."""

import sys
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.schema import Content, ProcessingTask
from app.services.queue import TaskType

logger = get_logger(__name__)


def main():
    """Main function to retranscribe all podcasts."""
    # Create database session
    settings = get_settings()
    engine = create_engine(str(settings.database_url))
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Find all podcast content
        podcasts = session.query(Content).filter(Content.content_type == "podcast").all()

        logger.info(f"Found {len(podcasts)} podcasts to retranscribe")

        # Create transcribe tasks for each podcast
        tasks_created = 0
        for podcast in podcasts:
            # Check if audio file exists
            metadata = podcast.content_metadata or {}
            audio_file_path = metadata.get("audio_file_path")

            if not audio_file_path:
                logger.warning(f"Podcast {podcast.id} has no audio file path, skipping")
                continue

            if not Path(audio_file_path).exists():
                logger.warning(f"Audio file not found for podcast {podcast.id}: {audio_file_path}")
                continue

            # Create transcribe task
            task = ProcessingTask(
                task_type=TaskType.TRANSCRIBE.value,
                content_id=podcast.id,
                payload={"audio_file_path": audio_file_path, "force_retranscribe": True},
                status="pending",
            )
            session.add(task)
            tasks_created += 1

            # Log progress
            logger.info(f"Created transcribe task for podcast {podcast.id}: {podcast.title}")

        # Commit all tasks
        session.commit()
        logger.info(f"Successfully created {tasks_created} transcribe tasks")

    except Exception as e:
        logger.error(f"Error creating transcribe tasks: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
