#!/usr/bin/env python3
"""
Script to test processing a single content item through the pipeline.
Usage: python scripts/test_single_content.py <url>
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime

from app.core.db import get_session_factory, init_db
from app.models.schema import Content, ContentStatus
from app.pipeline.worker import ContentWorker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


async def test_single_content(url: str):
    """Test processing a single content item."""
    # Initialize database
    init_db()
    SessionLocal = get_session_factory()
    db = SessionLocal()
    
    try:
        # Check if content already exists
        existing = db.query(Content).filter(Content.url == url).first()
        
        if existing:
            logger.info(f"Found existing content with ID {existing.id}, URL: {url}")
            content = existing
            # Reset status to pending for reprocessing
            content.status = ContentStatus.PENDING
            content.error = None
            content.processed_at = None
            db.commit()
            logger.info(f"Reset content {content.id} to PENDING status for reprocessing")
        else:
            # Create new content item
            content = Content(
                url=url,
                title=f"Test Content - {url}",
                status=ContentStatus.PENDING,
                created_at=datetime.utcnow(),
                platform="generic"  # Will be updated by processor
            )
            db.add(content)
            db.commit()
            db.refresh(content)
            logger.info(f"Created new content with ID {content.id}, URL: {url}")
        
        # Initialize worker
        worker = ContentWorker()
        
        # Process single content item
        logger.info(f"Starting processing for content ID {content.id}")
        result = worker.process_content(content.id, worker_id="test_script")
        
        # Refresh from database to get updated data
        db.refresh(content)
        
        # Print results
        print("\n" + "="*60)
        print("PROCESSING RESULTS")
        print("="*60)
        print(f"Content ID: {content.id}")
        print(f"URL: {content.url}")
        print(f"Status: {content.status.value}")
        print(f"Platform: {content.platform}")
        
        if content.title:
            print(f"Title: {content.title}")
        
        if content.summary:
            print("\nSummary Preview (first 500 chars):")
            print(content.summary[:500])
        
        if content.structured_summary:
            print("\nStructured Summary Available: Yes")
            import json
            try:
                summary_data = json.loads(content.structured_summary)
                print(f"  - Title: {summary_data.get('title', 'N/A')}")
                print(f"  - Classification: {summary_data.get('classification', 'N/A')}")
                print(f"  - Topics: {', '.join(summary_data.get('topics', []))}")
                print(f"  - Bullet Points: {len(summary_data.get('bullet_points', []))} items")
                print(f"  - Quotes: {len(summary_data.get('quotes', []))} items")
            except json.JSONDecodeError:
                print("  (Could not parse structured summary)")
        else:
            print("\nStructured Summary Available: No")
        
        if content.error:
            print(f"\nError: {content.error}")
        
        print(f"\nProcessed At: {content.processed_at}")
        print("="*60)
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing content: {e}", exc_info=True)
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/test_single_content.py <url>")
        print("Example: python scripts/test_single_content.py https://xbow.com/blog/gpt-5")
        sys.exit(1)
    
    url = sys.argv[1]
    
    if not url.startswith(('http://', 'https://')):
        print("Error: URL must start with http:// or https://")
        sys.exit(1)
    
    print(f"Testing content processing for URL: {url}")
    print("-" * 60)
    
    try:
        result = asyncio.run(test_single_content(url))
        if result:
            print("\n✅ Processing completed successfully!")
        else:
            print("\n⚠️ Processing completed with warnings or no result")
    except KeyboardInterrupt:
        print("\n\n❌ Processing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Processing failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()