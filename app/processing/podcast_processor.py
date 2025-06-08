import asyncio
from datetime import datetime
from typing import Dict, List
from app.database import SessionLocal
from app.models import Podcasts, PodcastStatus
from app.queue import download_podcast_task, transcribe_podcast_task, summarize_podcast_task
from app.config import logger

class PodcastProcessor:
    """
    Orchestrates the full podcast processing pipeline:
    1. Download audio files
    2. Transcribe to text
    3. Summarize content
    """
    
    def __init__(self):
        pass

    def process_new_podcasts(self) -> Dict[str, int]:
        """
        Process all podcasts with status 'new' by queuing download tasks.
        
        Returns:
            Dictionary with processing statistics
        """
        db = SessionLocal()
        try:
            new_podcasts = db.query(Podcasts).filter(Podcasts.status == PodcastStatus.new).all()
            
            if not new_podcasts:
                logger.info("No new podcasts to process")
                return {"queued": 0, "total": 0}

            queued = 0
            for podcast in new_podcasts:
                try:
                    # Queue download task
                    download_podcast_task(podcast.id)
                    queued += 1
                    logger.info(f"Queued download for podcast: {podcast.title}")
                except Exception as e:
                    logger.error(f"Error queuing download for podcast {podcast.id}: {e}")

            logger.info(f"Queued {queued} podcasts for download")
            return {"queued": queued, "total": len(new_podcasts)}

        except Exception as e:
            logger.error(f"Error in process_new_podcasts: {e}", exc_info=True)
            return {"queued": 0, "total": 0}
        finally:
            db.close()

    def process_downloaded_podcasts(self) -> Dict[str, int]:
        """
        Process all podcasts with status 'downloaded' by queuing transcription tasks.
        
        Returns:
            Dictionary with processing statistics
        """
        db = SessionLocal()
        try:
            downloaded_podcasts = db.query(Podcasts).filter(
                Podcasts.status == PodcastStatus.downloaded
            ).all()
            
            if not downloaded_podcasts:
                logger.info("No downloaded podcasts to transcribe")
                return {"queued": 0, "total": 0}

            queued = 0
            for podcast in downloaded_podcasts:
                try:
                    # Queue transcription task
                    transcribe_podcast_task(podcast.id)
                    queued += 1
                    logger.info(f"Queued transcription for podcast: {podcast.title}")
                except Exception as e:
                    logger.error(f"Error queuing transcription for podcast {podcast.id}: {e}")

            logger.info(f"Queued {queued} podcasts for transcription")
            return {"queued": queued, "total": len(downloaded_podcasts)}

        except Exception as e:
            logger.error(f"Error in process_downloaded_podcasts: {e}", exc_info=True)
            return {"queued": 0, "total": 0}
        finally:
            db.close()

    def process_transcribed_podcasts(self) -> Dict[str, int]:
        """
        Process all podcasts with status 'transcribed' by queuing summarization tasks.
        
        Returns:
            Dictionary with processing statistics
        """
        db = SessionLocal()
        try:
            transcribed_podcasts = db.query(Podcasts).filter(
                Podcasts.status == PodcastStatus.transcribed
            ).all()
            
            if not transcribed_podcasts:
                logger.info("No transcribed podcasts to summarize")
                return {"queued": 0, "total": 0}

            queued = 0
            for podcast in transcribed_podcasts:
                try:
                    # Queue summarization task
                    summarize_podcast_task(podcast.id)
                    queued += 1
                    logger.info(f"Queued summarization for podcast: {podcast.title}")
                except Exception as e:
                    logger.error(f"Error queuing summarization for podcast {podcast.id}: {e}")

            logger.info(f"Queued {queued} podcasts for summarization")
            return {"queued": queued, "total": len(transcribed_podcasts)}

        except Exception as e:
            logger.error(f"Error in process_transcribed_podcasts: {e}", exc_info=True)
            return {"queued": 0, "total": 0}
        finally:
            db.close()

    def process_all_pending_podcasts(self) -> Dict[str, Dict[str, int]]:
        """
        Process all pending podcasts in all stages of the pipeline.
        
        Returns:
            Dictionary with processing statistics for each stage
        """
        logger.info("Starting full podcast processing pipeline")
        
        results = {
            "downloads": self.process_new_podcasts(),
            "transcriptions": self.process_downloaded_podcasts(),
            "summaries": self.process_transcribed_podcasts()
        }
        
        total_queued = (
            results["downloads"]["queued"] + 
            results["transcriptions"]["queued"] + 
            results["summaries"]["queued"]
        )
        
        logger.info(f"Full pipeline processing complete. Total tasks queued: {total_queued}")
        return results

    def get_podcast_stats(self) -> Dict[str, int]:
        """
        Get statistics about podcasts in different states.
        
        Returns:
            Dictionary with podcast counts by status
        """
        db = SessionLocal()
        try:
            stats = {}
            for status in PodcastStatus:
                count = db.query(Podcasts).filter(Podcasts.status == status).count()
                stats[status.value] = count
            
            stats["total"] = db.query(Podcasts).count()
            return stats

        except Exception as e:
            logger.error(f"Error getting podcast stats: {e}", exc_info=True)
            return {}
        finally:
            db.close()

def process_new_podcasts() -> Dict[str, int]:
    """
    Convenience function to process new podcasts.
    """
    processor = PodcastProcessor()
    return processor.process_new_podcasts()

def process_all_pending_podcasts() -> Dict[str, Dict[str, int]]:
    """
    Convenience function to process all pending podcasts.
    """
    processor = PodcastProcessor()
    return processor.process_all_pending_podcasts()