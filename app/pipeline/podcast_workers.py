import os
import re
from datetime import datetime
from urllib.parse import unquote, urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.domain.converters import content_to_domain, domain_to_content
from app.models.schema import Content, ContentStatus
from app.services.queue import TaskType, get_queue_service
from app.utils.error_logger import create_error_logger

logger = get_logger(__name__)
settings = get_settings()


def sanitize_filename(title: str) -> str:
    """Sanitizes a title to be a valid filename."""
    # Remove invalid characters
    sanitized = re.sub(r"[^\w\s-]", "", title).strip()
    # Replace spaces with hyphens
    sanitized = re.sub(r"[-\s]+", "-", sanitized)
    # Truncate to a reasonable length
    return sanitized[:100]


def get_file_extension_from_url(url: str) -> str:
    """Extract file extension from URL."""
    parsed = urlparse(url)
    path = parsed.path
    if "." in path:
        return os.path.splitext(path)[1]
    return ".mp3"  # Default to mp3


class PodcastDownloadWorker:
    """Worker for downloading podcast audio files."""

    def __init__(self):
        self.base_dir = "data/podcasts"
        os.makedirs(self.base_dir, exist_ok=True)
        self.queue_service = get_queue_service()
        self.error_logger = create_error_logger("podcast_download_worker")

    def _validate_url(self, url: str) -> bool:
        """Validate URL format and basic reachability."""
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                logger.error(f"Invalid URL format: {url}")
                return False

            # Check for obvious invalid characters
            if any(char in url for char in [" ", "\n", "\r", "\t"]):
                logger.error(f"URL contains invalid characters: {url}")
                return False

            return True
        except Exception as e:
            logger.error(f"URL validation failed for {url}: {e}")
            return False

    def _extract_actual_audio_url(self, url: str) -> str:
        """
        Extract the actual audio URL from redirect URLs.

        Some podcast platforms (like Anchor.fm) use redirect URLs that contain
        the actual audio URL as an encoded parameter.
        """
        # Check if this is an Anchor.fm redirect URL
        if "anchor.fm" in url and "https%3A%2F%2F" in url:
            # Find the encoded URL in the path
            parts = url.split("/")
            for part in parts:
                if "https%3A%2F%2F" in part:
                    # Decode the URL
                    decoded_url = unquote(part)
                    logger.info(f"Extracted actual URL from Anchor redirect: {decoded_url}")
                    return decoded_url

        return url

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        retry=retry_if_exception_type(
            (
                httpx.ConnectError,
                httpx.TimeoutException,
                OSError,  # This includes DNS resolution errors
            )
        ),
    )
    def _download_with_retry(self, audio_url: str, file_path: str) -> None:
        """Download file with retry logic for network issues."""
        logger.info(f"Attempting download from {audio_url}")

        # Use sync httpx client with proper timeout configuration
        timeout = httpx.Timeout(
            timeout=300.0,  # Default timeout
            connect=30.0,  # DNS resolution timeout
            read=300.0,  # Large file download timeout
            write=30.0,
            pool=10.0,
        )

        headers = {"User-Agent": "Mozilla/5.0 (compatible; NewsAggregator/1.0; Podcast Downloader)"}

        with httpx.Client(
            timeout=timeout, follow_redirects=True, headers=headers
        ) as client:
            # First, try a HEAD request to validate the URL
            try:
                head_response = client.head(audio_url)
                head_response.raise_for_status()
                content_length = head_response.headers.get("content-length", "unknown")
                logger.info(f"URL validated, content-length: {content_length}")
            except Exception as e:
                logger.warning(f"HEAD request failed, proceeding with GET: {e}")

            # Download the file
            with client.stream("GET", audio_url) as response:
                response.raise_for_status()

                # Create directory if it doesn't exist
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

                # Write file in chunks
                with open(file_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

                logger.info(f"Downloaded {os.path.getsize(file_path)} bytes to {file_path}")

    def process_download_task(self, content_id: int) -> bool:
        """
        Download a podcast audio file.

        Args:
            content_id: ID of the content to download

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing download task for content {content_id}")
        file_path = None

        try:
            with get_db() as db:
                # Get content
                db_content = db.query(Content).filter(Content.id == content_id).first()

                if not db_content:
                    logger.error(f"Content {content_id} not found")
                    return False

                content = content_to_domain(db_content)

                # Get audio URL from metadata
                audio_url = content.metadata.get("audio_url")
                if not audio_url:
                    logger.error(f"No audio URL found for content {content_id}")
                    db_content.status = ContentStatus.FAILED.value
                    db_content.error_message = "No audio URL found"
                    db.commit()
                    return False

                # Extract actual audio URL if it's a redirect
                audio_url = self._extract_actual_audio_url(audio_url)

                # Validate URL format
                if not self._validate_url(audio_url):
                    logger.error(f"Invalid audio URL for content {content_id}: {audio_url}")
                    db_content.status = ContentStatus.FAILED.value
                    db_content.error_message = "Invalid audio URL format"
                    db.commit()
                    return False

                # Get podcast feed name from metadata (try multiple keys)
                feed_name = (
                    content.metadata.get("feed_name")
                    or content.metadata.get("podcast_feed_name")
                    or "unknown_feed"
                )

                # Create directory structure
                feed_dir = os.path.join(self.base_dir, sanitize_filename(feed_name))
                os.makedirs(feed_dir, exist_ok=True)

                # Determine file extension and create file path
                file_extension = get_file_extension_from_url(audio_url)
                sanitized_title = sanitize_filename(content.title or f"podcast_{content_id}")
                filename = f"{sanitized_title}{file_extension}"
                file_path = os.path.join(feed_dir, filename)

                # Check if file already exists
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    logger.info(f"File already exists: {file_path}")
                    content.metadata["file_path"] = file_path
                    content.metadata["download_date"] = datetime.utcnow().isoformat()
                    content.metadata["file_size"] = os.path.getsize(file_path)

                    # Update database
                    domain_to_content(content, db_content)
                    db.commit()

                    # Queue transcription task
                    self.queue_service.enqueue(TaskType.TRANSCRIBE, content_id=content_id)

                    return True

                # Download the audio file with retry logic
                self._download_with_retry(audio_url, file_path)

                # Verify file was written correctly
                if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                    raise Exception("Downloaded file is empty or doesn't exist")

                # Update content metadata
                content.metadata["file_path"] = file_path
                content.metadata["download_date"] = datetime.utcnow().isoformat()
                content.metadata["file_size"] = os.path.getsize(file_path)

                # Update database
                domain_to_content(content, db_content)
                db.commit()

                file_size = os.path.getsize(file_path)
                logger.info(f"Successfully downloaded podcast to {file_path} ({file_size} bytes)")

                # Queue transcription task
                self.queue_service.enqueue(TaskType.TRANSCRIBE, content_id=content_id)

                return True

        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error downloading podcast {content_id}: {error_msg}")

            # Log detailed error information
            self.error_logger.log_processing_error(
                item_id=content_id,
                error=e,
                operation="podcast_download",
                context={
                    "audio_url": audio_url if "audio_url" in locals() else None,
                    "file_path": file_path,
                    "error_type": type(e).__name__,
                },
            )

            # Clean up partial download if exists
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up partial download: {file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up partial download: {cleanup_error}")

            # Update content with error
            try:
                with get_db() as db:
                    db_content = db.query(Content).filter(Content.id == content_id).first()
                    if db_content:
                        db_content.status = ContentStatus.FAILED.value
                        db_content.error_message = error_msg[:500]  # Limit error message length
                        db_content.retry_count += 1
                        db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update database with error: {db_error}")

            return False


class PodcastTranscribeWorker:
    """Worker for transcribing podcast audio files."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None
        self.queue_service = get_queue_service()

    def _load_model(self):
        """Lazy load the Whisper model to save memory."""
        if self.model is None:
            try:
                from faster_whisper import WhisperModel

                logger.info(f"Loading Whisper model: {self.model_size}")
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                logger.info("Whisper model loaded successfully")
            except ImportError:
                logger.error("faster-whisper not installed. Install with: uv add faster-whisper")
                raise

    def process_transcribe_task(self, content_id: int) -> bool:
        """
        Transcribe a podcast audio file.

        Args:
            content_id: ID of the content to transcribe

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Processing transcribe task for content {content_id}")

        try:
            with get_db() as db:
                # Get content
                db_content = db.query(Content).filter(Content.id == content_id).first()

                if not db_content:
                    logger.error(f"Content {content_id} not found")
                    return False

                content = content_to_domain(db_content)

                # Get file path from metadata
                file_path = content.metadata.get("file_path")
                if not file_path or not os.path.exists(file_path):
                    error_msg = f"Audio file not found: {file_path}"
                    logger.error(error_msg)
                    db_content.status = ContentStatus.FAILED.value
                    db_content.error_message = error_msg
                    db.commit()
                    return False

                # Load model and transcribe
                self._load_model()

                logger.info(f"Starting transcription of: {file_path}")

                # Transcribe the audio
                segments, info = self.model.transcribe(file_path, beam_size=5)

                # Collect all text segments
                transcript_text = ""
                for segment in segments:
                    transcript_text += segment.text + " "

                # Create text file path (same directory as audio, but with .txt extension)
                base_path = os.path.splitext(file_path)[0]
                text_path = f"{base_path}.txt"

                # Write transcript to file
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(transcript_text.strip())

                logger.info(f"Transcription completed: {text_path}")
                lang_prob = f"{info.language_probability:.2f}"
                logger.info(f"Detected language: {info.language} (probability: {lang_prob})")

                # Update content metadata
                content.metadata["transcript_path"] = text_path
                content.metadata["transcript"] = transcript_text.strip()
                content.metadata["transcription_date"] = datetime.utcnow().isoformat()
                content.metadata["detected_language"] = info.language
                content.metadata["language_probability"] = info.language_probability

                # Update database
                domain_to_content(content, db_content)
                db.commit()

                logger.info(f"Successfully transcribed podcast {content_id}")

                # Queue summarization task
                self.queue_service.enqueue(TaskType.SUMMARIZE, content_id=content_id)

                return True

        except Exception as e:
            logger.error(f"Error transcribing podcast {content_id}: {e}")

            # Update content with error
            try:
                with get_db() as db:
                    db_content = db.query(Content).filter(Content.id == content_id).first()
                    if db_content:
                        db_content.status = ContentStatus.FAILED.value
                        db_content.error_message = str(e)
                        db_content.retry_count += 1
                        db.commit()
            except Exception:
                pass

            return False

    def cleanup_model(self):
        """Clean up the loaded model to free memory."""
        if self.model is not None:
            del self.model
            self.model = None
            logger.info("Whisper model cleaned up")
