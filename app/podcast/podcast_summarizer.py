"""
Podcast summarizer for generating summaries from transcribed podcast content.
Uses checkout/checkin mechanism for worker concurrency control.
"""

import os
from typing import Optional
from app.database import SessionLocal
from app.models import PodcastStatus
from app.config import logger
from app.podcast.checkout_manager import CheckoutManager
from app.constants import generate_worker_id, WORKER_SUMMARIZER
from app import llm


class PodcastSummarizer:
    """Summarizes podcast transcripts using LLM."""
    
    def __init__(self, instance_id: str = "1"):
        """
        Initialize the podcast summarizer.
        
        Args:
            instance_id: Instance identifier for worker ID generation
        """
        self.worker_id = generate_worker_id(WORKER_SUMMARIZER, instance_id)
    
    def summarize_podcast(self, podcast_id: int, worker_id: Optional[str] = None) -> bool:
        """
        Summarize a podcast transcript using checkout/checkin mechanism.
        
        Args:
            podcast_id: ID of the podcast to summarize
            worker_id: Optional worker ID (uses instance worker_id if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if worker_id is None:
            worker_id = self.worker_id
            
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            # Checkout podcast with transcribed state
            podcast = checkout_manager.checkout_podcast(podcast_id, worker_id, PodcastStatus.transcribed)
            if not podcast:
                logger.debug(f"Could not checkout podcast {podcast_id} for summarization")
                return False

            logger.info(f"Summarizing podcast: {podcast.title} (checked out by {worker_id})")

            try:
                if not podcast.transcribed_text_path or not os.path.exists(podcast.transcribed_text_path):
                    error_msg = f"Transcript file not found: {podcast.transcribed_text_path}"
                    logger.error(error_msg)
                    checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, error_msg)
                    return False

                # Read transcript content
                with open(podcast.transcribed_text_path, 'r', encoding='utf-8') as f:
                    transcript_text = f.read()

                # Generate summary using LLM
                summaries = llm.summarize_podcast_transcript(transcript_text)
                
                # Update podcast record fields
                podcast.short_summary = summaries.short_summary
                podcast.detailed_summary = summaries.detailed_summary
                podcast.error_message = None
                
                # Checkin with summarized state
                success = checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.summarized)
                if success:
                    logger.info(f"Successfully summarized and checked in podcast: {podcast.title}")
                    return True
                else:
                    logger.error(f"Failed to checkin podcast {podcast_id} after successful summarization")
                    return False

            except Exception as e:
                error_msg = f"Error summarizing podcast: {str(e)}"
                logger.error(f"Error summarizing podcast {podcast_id}: {error_msg}", exc_info=True)
                checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, error_msg)
                return False

        except Exception as e:
            logger.error(f"Error in summarize_podcast for ID {podcast_id}: {e}", exc_info=True)
            # Attempt to checkin with failed state if we have the worker_id
            if 'checkout_manager' in locals() and 'worker_id' in locals():
                checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, str(e))
            return False
        finally:
            db.close()
    
    def process_available_podcasts(self, limit: int = 3) -> dict:
        """
        Process available podcasts for summarization using checkout mechanism.
        
        Args:
            limit: Maximum number of podcasts to process
            
        Returns:
            Dictionary with processing statistics
        """
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            # Find available podcasts for summarization
            available_podcasts = checkout_manager.find_available_podcasts(PodcastStatus.transcribed, limit)
            
            if not available_podcasts:
                logger.debug("No transcribed podcasts available for summarization")
                return {"summarized": 0, "failed": 0, "total": 0}

            summarized = 0
            failed = 0
            
            for podcast in available_podcasts:
                success = self.summarize_podcast(podcast.id)
                if success:
                    summarized += 1
                else:
                    failed += 1

            logger.info(f"Summarization batch complete: {summarized} summarized, {failed} failed out of {len(available_podcasts)} available")
            return {"summarized": summarized, "failed": failed, "total": len(available_podcasts)}

        except Exception as e:
            logger.error(f"Error in process_available_podcasts: {e}", exc_info=True)
            return {"summarized": 0, "failed": 0, "total": 0}
        finally:
            db.close()