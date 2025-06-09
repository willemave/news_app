"""
Queue management using Huey for background task processing.
Handles LLM summarization tasks and link processing to avoid blocking the main scraping process.
"""
import os
from datetime import datetime
from huey import SqliteHuey

from .config import settings, logger
from .database import SessionLocal
from .models import Articles, ArticleStatus, Podcasts, PodcastStatus
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
    from .http_client.robust_http_client import RobustHttpClient
    from .processing_strategies.factory import UrlProcessorFactory
    from google.genai.errors import ClientError
    
    # Fetch the link from database
    db = SessionLocal()
    try:
        link = db.query(Links).filter(Links.id == link_id).first()
        if not link:
            logger.error(f"Link with ID {link_id} not found")
            return False
        
        # Initialize HTTP client and factory for synchronous processing
        http_client = RobustHttpClient(
            timeout=settings.HTTP_CLIENT_TIMEOUT,
            headers={'User-Agent': settings.HTTP_CLIENT_USER_AGENT}
        )
        factory = UrlProcessorFactory(http_client)
        
        try:
            return process_link_from_db(link, http_client, factory)
        finally:
            http_client.close()
        
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

@huey.task(retries=3, retry_delay=60)
def download_podcast_task(podcast_id: int) -> bool:
    """
    Background task to download a podcast audio file.
    Automatically queues transcription task on successful download.
    
    Args:
        podcast_id: ID of the podcast to download
    
    Returns:
        True if successful, False otherwise
    """
    from .processing.podcast_downloader import PodcastDownloader
    
    try:
        # http_client parameter is no longer used by PodcastDownloader
        downloader = PodcastDownloader()
        result = downloader.download_podcast(podcast_id)
        
        # If download was successful, automatically queue transcription
        if result:
            logger.info(f"Download successful for podcast {podcast_id}, queuing transcription...")
            transcribe_podcast_task(podcast_id)
        
        return result
    except Exception as e:
        logger.error(f"Error in download_podcast_task for ID {podcast_id}: {e}", exc_info=True)
        return False

@huey.task(retries=2, retry_delay=120)
def transcribe_podcast_task(podcast_id: int) -> bool:
    """
    Background task to transcribe a podcast audio file to text.
    Automatically queues summarization task on successful transcription.
    
    Args:
        podcast_id: ID of the podcast to transcribe
    
    Returns:
        True if successful, False otherwise
    """
    from .processing.podcast_converter import PodcastConverter
    
    try:
        converter = PodcastConverter(model_size="distil-large-v3")
        try:
            result = converter.transcribe_podcast(podcast_id)
        finally:
            converter.cleanup_model()
        
        # If transcription was successful, automatically queue summarization
        if result:
            logger.info(f"Transcription successful for podcast {podcast_id}, queuing summarization...")
            summarize_podcast_task(podcast_id)
        
        return result
    except Exception as e:
        logger.error(f"Error in transcribe_podcast_task for ID {podcast_id}: {e}", exc_info=True)
        return False

@huey.task(retries=3, retry_delay=60)
def summarize_podcast_task(podcast_id: int) -> bool:
    """
    Background task to summarize a podcast transcript and update database.
    
    Args:
        podcast_id: ID of the podcast to summarize
    
    Returns:
        True if successful, False otherwise
    """
    db = SessionLocal()
    
    try:
        # Retrieve the podcast record
        podcast = db.query(Podcasts).filter(Podcasts.id == podcast_id).first()
        if not podcast:
            logger.error(f"Podcast with ID {podcast_id} not found")
            return False
        
        if podcast.status != PodcastStatus.transcribed:
            logger.warning(f"Podcast {podcast_id} is not in transcribed status (current: {podcast.status})")
            return False
        
        if not podcast.transcribed_text_path or not os.path.exists(podcast.transcribed_text_path):
            error_msg = f"Transcript file not found: {podcast.transcribed_text_path}"
            logger.error(error_msg)
            podcast.status = PodcastStatus.failed
            podcast.error_message = error_msg
            db.commit()
            return False
        
        logger.info(f"Processing summarization for podcast {podcast_id}: {podcast.title}")
        
        # Read transcript content
        with open(podcast.transcribed_text_path, 'r', encoding='utf-8') as f:
            transcript_text = f.read()
        
        # Generate summary using LLM
        summaries = llm.summarize_podcast_transcript(transcript_text)
        
        # Update podcast with summary data
        podcast.short_summary = summaries.short_summary
        podcast.detailed_summary = summaries.detailed_summary
        podcast.status = PodcastStatus.summarized
        podcast.error_message = None
        
        # Commit changes
        db.commit()
        
        logger.info(f"Successfully summarized podcast {podcast_id}: {podcast.title}")
        return True
        
    except Exception as e:
        error_msg = f"Error summarizing podcast {podcast_id}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Update podcast status to failed
        try:
            podcast = db.query(Podcasts).filter(Podcasts.id == podcast_id).first()
            if podcast:
                podcast.status = PodcastStatus.failed
                podcast.error_message = error_msg
                db.commit()
        except:
            pass
        
        db.rollback()
        return False
        
    finally:
        db.close()
