#!/usr/bin/env python3
"""
Re-run summarization on all downloaded content using Google Flash 2.5.

This script will:
1. Find all content that has been downloaded (has text content or transcript)
2. Re-generate structured summaries using the new Google LLM provider
3. Update the content metadata with new summaries
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.db import get_db
from app.core.logging import get_logger
from app.models.schema import Content
from app.services.llm import get_llm_service
from app.core.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


async def resummarize_content(content_id: int, llm_service) -> bool:
    """Re-summarize a single content item."""
    try:
        with get_db() as db:
            # Get content
            db_content = db.query(Content).filter(Content.id == content_id).first()
            
            if not db_content:
                logger.error(f"Content {content_id} not found")
                return False
            
            # Determine what to summarize
            content_to_summarize = None
            
            if db_content.content_type == "article":
                # For articles, get the text content
                content_to_summarize = db_content.content_metadata.get('content', '') if db_content.content_metadata else ''
            elif db_content.content_type == "podcast":
                # For podcasts, get the transcript
                content_to_summarize = db_content.content_metadata.get('transcript', '') if db_content.content_metadata else ''
            
            if not content_to_summarize:
                logger.warning(f"No content to summarize for {content_id} ({db_content.title})")
                return False
            
            logger.info(f"Re-summarizing content {content_id}: {db_content.title}")
            
            # Generate new structured summary
            summary = await llm_service.summarize_content(content_to_summarize)
            
            if summary:
                # Update content metadata
                if not db_content.content_metadata:
                    db_content.content_metadata = {}
                
                # Create a mutable copy
                new_metadata = dict(db_content.content_metadata)
                
                # Convert to dict if it's a Pydantic model
                if hasattr(summary, 'model_dump'):
                    new_metadata['summary'] = summary.model_dump(mode='json')
                else:
                    new_metadata['summary'] = summary
                
                new_metadata['summarization_date'] = datetime.now(timezone.utc).isoformat()
                
                db_content.content_metadata = new_metadata
                db.commit()
                
                logger.info(f"Successfully re-summarized content {content_id}")
                return True
            else:
                logger.error(f"Failed to generate summary for content {content_id}")
                return False
                
    except Exception as e:
        logger.error(f"Error re-summarizing content {content_id}: {e}")
        return False


async def main():
    """Main function to re-summarize all content."""
    logger.info("Starting re-summarization script")
    
    # Check if Google API key is configured
    if not getattr(settings, 'google_api_key', None):
        logger.error("GOOGLE_API_KEY not configured in settings")
        print("Error: GOOGLE_API_KEY environment variable must be set")
        sys.exit(1)
    
    logger.info("Google API key is configured")
    
    # Initialize LLM service
    logger.info("Initializing LLM service")
    llm_service = get_llm_service()
    logger.info("LLM service initialized successfully")
    
    # Get all content that has been downloaded and needs summarization
    logger.info("Querying database for content to re-summarize")
    with get_db() as db:
        # Query for content that has text content or transcript
        query = db.query(Content).filter(
            Content.status.in_(['completed', 'processed'])
        )
        
        all_content = query.all()
        logger.info(f"Found {len(all_content)} total content items with status 'completed' or 'processed'")
        
        # Filter content that has something to summarize
        content_to_process = []
        articles_count = 0
        podcasts_count = 0
        
        for content in all_content:
            if content.content_metadata:
                if content.content_type == "article" and content.content_metadata.get('content'):
                    content_to_process.append(content)
                    articles_count += 1
                elif content.content_type == "podcast" and content.content_metadata.get('transcript'):
                    content_to_process.append(content)
                    podcasts_count += 1
        
        total = len(content_to_process)
        logger.info(f"Found {total} content items to re-summarize ({articles_count} articles, {podcasts_count} podcasts)")
        
        if total == 0:
            logger.info("No content found that needs re-summarization")
            print("No content found that needs re-summarization")
            return
        
        # Ask for confirmation
        logger.info(f"Requesting user confirmation to re-summarize {total} items")
        print(f"\nFound {total} content items to re-summarize using Google Gemini Flash 2.5")
        print("This will overwrite existing summaries.")
        response = input("Continue? (y/N): ")
        
        if response.lower() != 'y':
            logger.info("User aborted re-summarization process")
            print("Aborted")
            return
        
        logger.info("User confirmed, starting re-summarization process")
        
        # Process in batches to avoid overwhelming the API
        batch_size = 5
        successful = 0
        failed = 0
        
        logger.info(f"Starting batch processing with batch size {batch_size}")
        
        for i in range(0, total, batch_size):
            batch = content_to_process[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            logger.info(f"Processing batch {batch_num}/{total_batches} ({i+1}-{min(i+batch_size, total)} of {total})")
            
            # Log content IDs in batch
            batch_ids = [content.id for content in batch]
            logger.info(f"Batch {batch_num} content IDs: {batch_ids}")
            
            # Process batch concurrently
            tasks = [resummarize_content(content.id, llm_service) for content in batch]
            results = await asyncio.gather(*tasks)
            
            # Count results
            batch_successful = sum(1 for r in results if r)
            batch_failed = sum(1 for r in results if not r)
            
            successful += batch_successful
            failed += batch_failed
            
            logger.info(f"Batch {batch_num} complete: {batch_successful} successful, {batch_failed} failed")
            logger.info(f"Running totals: {successful} successful, {failed} failed")
            
            # Add a small delay between batches to be nice to the API
            if i + batch_size < total:
                logger.info("Waiting 1 second before next batch")
                await asyncio.sleep(1)
        
        # Final report
        logger.info("Re-summarization process completed")
        logger.info(f"Final results: {successful} successful, {failed} failed out of {total} total")
        
        print(f"\n=== Re-summarization Complete ===")
        print(f"Total processed: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
        if failed > 0:
            logger.warning(f"{failed} items failed to re-summarize")
            print(f"\nCheck logs for details on failed items")
        else:
            logger.info("All items successfully re-summarized")


if __name__ == "__main__":
    logger.info("Script started")
    try:
        asyncio.run(main())
        logger.info("Script completed successfully")
    except Exception as e:
        logger.error(f"Script failed with error: {e}")
        raise