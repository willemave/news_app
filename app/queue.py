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
