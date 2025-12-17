import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.db import get_db
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.domain.converters import content_to_domain, domain_to_content
from app.models.schema import Content, ContentStatus
from app.services.queue import TaskType, get_queue_service
from app.services.whisper_local import get_whisper_local_service

# Resolve project root (two levels up from this file: app/ → project root)
PROJECT_ROOT = Path(__file__).resolve().parents[2]

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
        # Resolve to an absolute path so downstream workers can rely on it even if
        # the process is started from a different working directory.
        self.base_dir = settings.podcast_media_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.queue_service = get_queue_service()

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
    def _download_with_retry(self, audio_url: str, file_path: Path) -> None:
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

        with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
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
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file in chunks
                with open(file_path, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=8192):
                        f.write(chunk)

                logger.info(f"Downloaded {file_path.stat().st_size} bytes to {file_path}")

    def _is_youtube_url(self, url: str) -> bool:
        """Check if URL is a YouTube URL."""
        youtube_patterns = [
            r"youtube\.com/watch\?v=",
            r"youtu\.be/",
            r"youtube\.com/embed/",
            r"m\.youtube\.com/watch\?v=",
            r"youtube\.com/v/",
            r"youtube\.com/shorts/",
        ]
        return any(re.search(pattern, url) for pattern in youtube_patterns)

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

                # Check if this is a YouTube URL
                if self._is_youtube_url(audio_url):
                    logger.info(f"Detected YouTube URL for content {content_id}, skipping download")

                    # Update metadata to indicate no download needed
                    content.metadata["youtube_video"] = True
                    content.metadata["download_skipped"] = True
                    content.metadata["skip_reason"] = "YouTube videos processed without downloading"

                    # Update database
                    domain_to_content(content, db_content)
                    db.commit()

                    # Queue transcription task directly (transcriber will handle YouTube)
                    self.queue_service.enqueue(TaskType.TRANSCRIBE, content_id=content_id)

                    return True

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
                feed_dir = self.base_dir / sanitize_filename(feed_name)
                feed_dir.mkdir(parents=True, exist_ok=True)

                # Determine file extension and create file path
                file_extension = get_file_extension_from_url(audio_url)
                sanitized_title = sanitize_filename(content.title or f"podcast_{content_id}")
                filename = f"{sanitized_title}{file_extension}"
                file_path = feed_dir / filename

                # Check if file already exists
                if file_path.exists() and file_path.stat().st_size > 0:
                    logger.info(f"File already exists: {file_path}")
                    content.metadata["file_path"] = str(file_path)
                    content.metadata["download_date"] = datetime.utcnow().isoformat()
                    content.metadata["file_size"] = file_path.stat().st_size

                    # Update database
                    domain_to_content(content, db_content)
                    db.commit()

                    # Queue transcription task
                    self.queue_service.enqueue(TaskType.TRANSCRIBE, content_id=content_id)

                    return True

                # Download the audio file with retry logic
                self._download_with_retry(audio_url, file_path)

                # Verify file was written correctly
                if not file_path.exists() or file_path.stat().st_size == 0:
                    raise Exception("Downloaded file is empty or doesn't exist")

                # Update content metadata
                content.metadata["file_path"] = str(file_path)
                content.metadata["download_date"] = datetime.utcnow().isoformat()
                content.metadata["file_size"] = file_path.stat().st_size

                # Update database
                domain_to_content(content, db_content)
                db.commit()

                file_size = file_path.stat().st_size
                logger.info(f"Successfully downloaded podcast to {file_path} ({file_size} bytes)")

                # Queue transcription task
                self.queue_service.enqueue(TaskType.TRANSCRIBE, content_id=content_id)

                return True

        except Exception as e:
            error_msg = str(e)
            logger.exception(
                "Error downloading podcast %s: %s",
                content_id,
                error_msg,
                extra={
                    "component": "podcast_download_worker",
                    "operation": "podcast_download",
                    "item_id": content_id,
                    "context_data": {
                        "audio_url": audio_url if "audio_url" in locals() else None,
                        "file_path": str(file_path) if file_path else None,
                        "error_type": type(e).__name__,
                    },
                },
            )

            # Clean up partial download if exists
            if file_path and Path(file_path).exists():
                try:
                    Path(file_path).unlink()
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
    """Worker for transcribing podcast audio files using OpenAI."""

    def __init__(self):
        self.base_dir = settings.podcast_media_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.queue_service = get_queue_service()
        self.transcription_service = None

    def _get_transcription_service(self):
        """Lazy load the transcription service."""
        if self.transcription_service is None:
            try:
                self.transcription_service = get_whisper_local_service()
                logger.info("Local Whisper transcription service initialized")
            except Exception as e:
                logger.error(f"Failed to initialize transcription service: {e}")
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

                # Check if this is a YouTube video with existing transcript
                if content.metadata.get("youtube_video") and content.metadata.get("transcript"):
                    logger.info(f"Using existing YouTube transcript for content {content_id}")

                    # YouTube transcript already available from strategy processing
                    transcript_text = content.metadata.get("transcript")

                    # Create directory for YouTube transcripts
                    youtube_dir = self.base_dir / "youtube"
                    youtube_dir.mkdir(parents=True, exist_ok=True)

                    # Create text file path
                    sanitized_title = sanitize_filename(content.title or f"youtube_{content_id}")
                    text_path = youtube_dir / f"{sanitized_title}.txt"

                    # Write transcript to file
                    with open(text_path, "w", encoding="utf-8") as f:
                        f.write(transcript_text.strip())

                    logger.info(f"YouTube transcript saved to: {text_path}")

                    # Update content metadata
                    content.metadata["transcript_path"] = str(text_path)
                    content.metadata["transcription_date"] = datetime.utcnow().isoformat()
                    content.metadata["transcription_service"] = "youtube"

                    # Update database
                    domain_to_content(content, db_content)
                    db.commit()

                    # Queue summarization task
                    self.queue_service.enqueue(TaskType.SUMMARIZE, content_id=content_id)

                    return True

                # Get file path from metadata for regular podcasts
                file_path_value = content.metadata.get("file_path")
                if not file_path_value:
                    error_msg = "Audio file path missing in metadata"
                    logger.error(error_msg)
                    db_content.status = ContentStatus.FAILED.value
                    db_content.error_message = error_msg
                    db.commit()
                    return False

                original_path = Path(file_path_value)
                if original_path.is_absolute():
                    audio_path = original_path
                else:
                    # Treat stored path as relative to the project root first
                    audio_path = (PROJECT_ROOT / original_path).resolve()

                    if not audio_path.exists():
                        parts = original_path.parts
                        if len(parts) >= 2 and parts[0:2] == ("data", "podcasts"):
                            tail = Path(*parts[2:])
                            audio_path = (self.base_dir / tail).resolve()
                        else:
                            audio_path = (self.base_dir / original_path).resolve()

                if not audio_path.exists():
                    error_msg = f"Audio file not found: {audio_path}"
                    logger.error(error_msg)
                    db_content.status = ContentStatus.FAILED.value
                    db_content.error_message = error_msg
                    db.commit()
                    return False

                # Normalise metadata so future retries use the absolute path
                if str(audio_path) != file_path_value:
                    content.metadata["file_path"] = str(audio_path)
                    domain_to_content(content, db_content)
                    db.commit()

                # Get transcription service and transcribe
                self._get_transcription_service()

                logger.info(f"Starting transcription of: {audio_path}")

                # Transcribe the audio
                transcript_text, detected_language = self.transcription_service.transcribe_audio(
                    audio_path
                )

                # Create text file path (same directory as audio, but with .txt extension)
                base_path = audio_path.with_suffix("")
                text_path = base_path.with_suffix(".txt")

                # Write transcript to file
                with open(text_path, "w", encoding="utf-8") as f:
                    f.write(transcript_text.strip())

                logger.info(f"Transcription completed: {text_path}")
                if detected_language:
                    logger.info(f"Detected language: {detected_language}")

                # Update content metadata
                content.metadata["transcript_path"] = str(text_path)
                content.metadata["transcript"] = transcript_text.strip()
                content.metadata["transcription_date"] = datetime.utcnow().isoformat()
                if detected_language:
                    content.metadata["detected_language"] = detected_language
                content.metadata["transcription_service"] = "whisper_local"

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

    def cleanup_service(self):
        """Clean up the transcription service."""
        if self.transcription_service is not None:
            # Clean up local whisper model
            if hasattr(self.transcription_service, "cleanup_service"):
                self.transcription_service.cleanup_service()
            self.transcription_service = None
        logger.info("Transcription service cleaned up")
