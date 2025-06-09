import os
import re
import httpx
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from app.database import SessionLocal
from app.models import Podcasts, PodcastStatus
from app.config import logger
from app.processing.checkout_manager import CheckoutManager
from app.processing.state_machine import PodcastStateMachine
from app.constants import generate_worker_id, WORKER_DOWNLOADER

def sanitize_filename(title: str) -> str:
    """Sanitizes a title to be a valid filename."""
    # Remove invalid characters
    sanitized = re.sub(r'[^\w\s-]', '', title).strip()
    # Replace spaces with hyphens
    sanitized = re.sub(r'[-\s]+', '-', sanitized)
    # Truncate to a reasonable length
    return sanitized[:100]

def get_file_extension_from_url(url: str) -> str:
    """Extract file extension from URL."""
    parsed = urlparse(url)
    path = parsed.path
    if '.' in path:
        return os.path.splitext(path)[1]
    return '.mp3'  # Default to mp3

class PodcastDownloader:
    def __init__(self, http_client=None, instance_id: str = "1"):
        # http_client parameter kept for compatibility but not used
        self.base_dir = "data/podcasts"
        os.makedirs(self.base_dir, exist_ok=True)
        self.worker_id = generate_worker_id(WORKER_DOWNLOADER, instance_id)

    def download_podcast(self, podcast_id: int, worker_id: Optional[str] = None) -> bool:
        """
        Download a podcast audio file using checkout/checkin mechanism.
        
        Args:
            podcast_id: ID of the podcast to download
            worker_id: Optional worker ID (uses instance worker_id if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if worker_id is None:
            worker_id = self.worker_id
            
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            # Checkout podcast with new state
            podcast = checkout_manager.checkout_podcast(podcast_id, worker_id, PodcastStatus.new)
            if not podcast:
                logger.debug(f"Could not checkout podcast {podcast_id} for download")
                return False

            logger.info(f"Downloading podcast: {podcast.title} (checked out by {worker_id})")

            try:
                # Create directory structure
                feed_dir = os.path.join(self.base_dir, sanitize_filename(podcast.podcast_feed_name))
                os.makedirs(feed_dir, exist_ok=True)

                # Determine file extension and create file path
                file_extension = get_file_extension_from_url(podcast.enclosure_url)
                sanitized_title = sanitize_filename(podcast.title)
                filename = f"{sanitized_title}{file_extension}"
                file_path = os.path.join(feed_dir, filename)

                # Check if file already exists
                if os.path.exists(file_path):
                    logger.info(f"File already exists: {file_path}")
                    podcast.file_path = file_path
                    podcast.download_date = datetime.utcnow()
                    podcast.error_message = None
                    
                    # Checkin with downloaded state
                    success = checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.downloaded)
                    if success:
                        logger.info(f"Successfully checked in existing podcast: {podcast.title}")
                        return True
                    else:
                        logger.error(f"Failed to checkin podcast {podcast_id} after finding existing file")
                        return False

                # Download the audio file
                with httpx.Client(timeout=300.0, follow_redirects=True) as client:
                    with client.stream('GET', podcast.enclosure_url) as response:
                        response.raise_for_status()
                        
                        # Write file in chunks to handle large files
                        with open(file_path, 'wb') as f:
                            for chunk in response.iter_bytes(chunk_size=8192):
                                f.write(chunk)

                # Verify file was written
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    raise Exception("Downloaded file is empty or doesn't exist")

                # Update podcast record fields
                podcast.file_path = file_path
                podcast.download_date = datetime.utcnow()
                podcast.error_message = None

                # Checkin with downloaded state
                success = checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.downloaded)
                if success:
                    logger.info(f"Successfully downloaded and checked in podcast: {podcast.title} to {file_path}")
                    return True
                else:
                    logger.error(f"Failed to checkin podcast {podcast_id} after successful download")
                    return False

            except Exception as e:
                # Clean up partial download
                if 'file_path' in locals() and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
                
                error_msg = f"Failed to download podcast audio: {str(e)}"
                logger.error(f"Error downloading podcast {podcast_id}: {error_msg}")
                
                # Checkin with failed state
                checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, error_msg)
                return False

        except Exception as e:
            logger.error(f"Error in download_podcast for ID {podcast_id}: {e}", exc_info=True)
            # Attempt to checkin with failed state if we have the worker_id
            if 'checkout_manager' in locals() and 'worker_id' in locals():
                checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, str(e))
            return False
        finally:
            db.close()

    def process_available_podcasts(self, limit: int = 10) -> dict:
        """
        Process available podcasts for download using checkout mechanism.
        
        Args:
            limit: Maximum number of podcasts to process
            
        Returns:
            Dictionary with processing statistics
        """
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            # Find available podcasts for download
            available_podcasts = checkout_manager.find_available_podcasts(PodcastStatus.new, limit)
            
            if not available_podcasts:
                logger.debug("No new podcasts available for download")
                return {"downloaded": 0, "failed": 0, "total": 0}

            downloaded = 0
            failed = 0
            
            for podcast in available_podcasts:
                success = self.download_podcast(podcast.id)
                if success:
                    downloaded += 1
                else:
                    failed += 1

            logger.info(f"Download batch complete: {downloaded} downloaded, {failed} failed out of {len(available_podcasts)} available")
            return {"downloaded": downloaded, "failed": failed, "total": len(available_podcasts)}

        except Exception as e:
            logger.error(f"Error in process_available_podcasts: {e}", exc_info=True)
            return {"downloaded": 0, "failed": 0, "total": 0}
        finally:
            db.close()