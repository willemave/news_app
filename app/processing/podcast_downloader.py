import os
import re
import httpx
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from app.database import SessionLocal
from app.models import Podcasts, PodcastStatus
from app.config import logger

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
    def __init__(self, http_client=None):
        # http_client parameter kept for compatibility but not used
        self.base_dir = "data/podcasts"
        os.makedirs(self.base_dir, exist_ok=True)

    async def download_podcast(self, podcast_id: int) -> bool:
        """
        Download a podcast audio file.
        
        Args:
            podcast_id: ID of the podcast to download
            
        Returns:
            True if successful, False otherwise
        """
        db = SessionLocal()
        try:
            # Get podcast record
            podcast = db.query(Podcasts).filter(Podcasts.id == podcast_id).first()
            if not podcast:
                logger.error(f"Podcast with ID {podcast_id} not found")
                return False

            if podcast.status != PodcastStatus.new:
                logger.info(f"Podcast {podcast_id} already processed (status: {podcast.status})")
                return True

            logger.info(f"Downloading podcast: {podcast.title}")

            # Update status to indicate download in progress
            podcast.status = PodcastStatus.new  # Keep as new until fully downloaded
            db.commit()

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
                podcast.status = PodcastStatus.downloaded
                podcast.download_date = datetime.utcnow()
                db.commit()
                return True

            # Download the audio file
            try:
                async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
                    async with client.stream('GET', podcast.enclosure_url) as response:
                        response.raise_for_status()
                        
                        # Write file in chunks to handle large files
                        with open(file_path, 'wb') as f:
                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                f.write(chunk)

                # Verify file was written
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    raise Exception("Downloaded file is empty or doesn't exist")

                # Update podcast record
                podcast.file_path = file_path
                podcast.status = PodcastStatus.downloaded
                podcast.download_date = datetime.utcnow()
                podcast.error_message = None
                db.commit()

                logger.info(f"Successfully downloaded podcast: {podcast.title} to {file_path}")
                return True

            except Exception as e:
                # Clean up partial download
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
                
                error_msg = f"Failed to download podcast audio: {str(e)}"
                logger.error(f"Error downloading podcast {podcast_id}: {error_msg}")
                
                podcast.status = PodcastStatus.failed
                podcast.error_message = error_msg
                db.commit()
                return False

        except Exception as e:
            logger.error(f"Error in download_podcast for ID {podcast_id}: {e}", exc_info=True)
            return False
        finally:
            db.close()

    async def download_all_new_podcasts(self) -> dict:
        """
        Download all podcasts with status 'new'.
        
        Returns:
            Dictionary with download statistics
        """
        db = SessionLocal()
        try:
            new_podcasts = db.query(Podcasts).filter(Podcasts.status == PodcastStatus.new).all()
            
            if not new_podcasts:
                logger.info("No new podcasts to download")
                return {"downloaded": 0, "failed": 0, "total": 0}

            downloaded = 0
            failed = 0
            
            for podcast in new_podcasts:
                success = await self.download_podcast(podcast.id)
                if success:
                    downloaded += 1
                else:
                    failed += 1

            logger.info(f"Download batch complete: {downloaded} downloaded, {failed} failed")
            return {"downloaded": downloaded, "failed": failed, "total": len(new_podcasts)}

        except Exception as e:
            logger.error(f"Error in download_all_new_podcasts: {e}", exc_info=True)
            return {"downloaded": 0, "failed": 0, "total": 0}
        finally:
            db.close()