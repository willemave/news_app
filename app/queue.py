"""
Queue management using Huey for background task processing.
Handles LLM summarization tasks and link processing to avoid blocking the main scraping process.
"""
import json
from datetime import datetime
from typing import Optional
from huey import SqliteHuey

from .config import settings, logger
from .database import SessionLocal
from .models import Articles, ArticleStatus
from . import llm


# Initialize Huey with SQLite backend
huey = SqliteHuey(filename=settings.HUEY_DB_PATH)


@huey.task(retries=3, retry_delay=60)
def process_link_task(link_id: int) -> bool:
    """
    Background task to process a link from the links table.
    Downloads content, processes with LLM, and creates Articles.
    
    Args:
        link_id: ID of the link to process
    
    Returns:
        True if successful, False otherwise
    """
    from .processor import process_link_from_db
    from .models import Links
    from google.genai.errors import ClientError
    
    # Fetch the link from database
    db = SessionLocal()
    try:
        link = db.query(Links).filter(Links.id == link_id).first()
        if not link:
            logger.error(f"Link with ID {link_id} not found")
            return False
        
        # Process the link
        return process_link_from_db(link)
        
    except ClientError as e:
        # Check if this is a 429 rate limit error
        if "429" in str(e) or "rate limit" in str(e).lower():
            logger.warning(f"LLM rate limit hit for link {link_id}, will retry: {e}")
            # Re-raise to trigger Huey's retry mechanism
            raise
        else:
            logger.error(f"LLM client error for link {link_id}: {e}", exc_info=True)
            return False
    except Exception as e:
        logger.error(f"Error processing link {link_id}: {e}", exc_info=True)
        return False
    finally:
        db.close()

@huey.task()
def summarize_task(article_id: int, raw_content: str, is_pdf: bool = False) -> bool:
    """
    Background task to summarize article content and update database.
    
    Args:
        article_id: ID of the article to summarize
        raw_content: Raw content (text for HTML, base64 bytes for PDF)
        is_pdf: Whether the content is a PDF file
    
    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    
    try:
        # Retrieve the article record
        article = db.query(Articles).filter(Articles.id == article_id).first()
        if not article:
            logger.error(f"Article with ID {article_id} not found")
            return False
        
        logger.info(f"Processing summarization for article {article_id}: {article.title}")
        
        # Generate summary based on content type
        if is_pdf:
            # For PDF content, raw_content should be base64 encoded bytes
            # Decode base64 string back to bytes for LLM processing
            import base64
            pdf_bytes = base64.b64decode(raw_content)
            summaries = llm.summarize_pdf(pdf_bytes)
        else:
            # For HTML content, use regular summarization
            summaries = llm.summarize_article(raw_content)
        
        # Handle both dict and tuple return formats for backward compatibility
        if isinstance(summaries, dict):
            short_summary = summaries.get("short", "")
            detailed_summary = summaries.get("detailed", "")
            keywords = summaries.get("keywords", [])
        else:
            # Fallback for tuple format
            short_summary = summaries[0] if len(summaries) > 0 else ""
            detailed_summary = summaries[1] if len(summaries) > 1 else ""
            keywords = []
        
        # Update article with summary data
        article.short_summary = short_summary
        article.detailed_summary = detailed_summary
        article.summary_date = datetime.utcnow()
        article.status = ArticleStatus.processed
        
        # Commit changes
        db.commit()
        
        logger.info(f"Successfully summarized article {article_id}: {article.title}")
        return True
        
    except Exception as e:
        logger.error(f"Error summarizing article {article_id}: {e}", exc_info=True)
        db.rollback()
        return False
        
    finally:
        db.close()


def drain_queue() -> None:
    """
    Drain the Huey queue by running all pending tasks.
    This is useful for scripts that need to wait for all tasks to complete.
    """
    logger.info("Starting to drain Huey queue...")
    
    processed_count = 0
    failed_count = 0
    
    while True:
        task = huey.dequeue()
        if not task:
            logger.info("No more tasks in the queue.")
            break
        
        try:
            # Execute the task directly using Huey's execute method
            result = huey.execute(task)
            processed_count += 1
        except Exception as e:
            failed_count += 1
            logger.error(f"Error processing task {getattr(task, 'id', 'N/A')} ({getattr(task, 'name', 'N/A')}): {e}", exc_info=True)

    if processed_count > 0 or failed_count > 0:
        logger.info(f"Queue draining finished. Processed: {processed_count}, Failed: {failed_count}.")
    else:
        logger.info("Queue was empty or no tasks were processed during drain.")


def get_queue_stats() -> dict:
    """
    Get statistics about the current queue state.
    
    Returns:
        Dictionary with queue statistics
    """
    try:
        # Get pending tasks count
        pending_count = len(huey.pending())
        
        return {
            "pending_tasks": pending_count,
            "queue_db_path": settings.HUEY_DB_PATH
        }
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        return {
            "pending_tasks": -1,
            "queue_db_path": settings.HUEY_DB_PATH,
            "error": str(e)
        }
