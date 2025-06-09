import os
from typing import Optional
from faster_whisper import WhisperModel
from app.database import SessionLocal
from app.models import PodcastStatus
from app.config import logger
from app.processing.checkout_manager import CheckoutManager
from app.constants import generate_worker_id, WORKER_TRANSCRIBER

class PodcastConverter:
    def __init__(self, model_size: str = "base", instance_id: str = "1"):
        """
        Initialize the podcast converter with a Whisper model.
        
        Args:
            model_size: Size of the Whisper model to use (tiny, base, small, medium, large)
            instance_id: Instance identifier for worker ID generation
        """
        self.model_size = model_size
        self.model = None
        self.worker_id = generate_worker_id(WORKER_TRANSCRIBER, instance_id)
        
    def _load_model(self):
        """Lazy load the Whisper model to save memory."""
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_size}")
            self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            logger.info("Whisper model loaded successfully")

    def convert_to_text(self, audio_path: str) -> Optional[str]:
        """
        Convert audio file to text using Whisper.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Path to the generated text file, or None if conversion failed
        """
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return None

        try:
            self._load_model()
            
            logger.info(f"Starting transcription of: {audio_path}")
            
            # Transcribe the audio
            segments, info = self.model.transcribe(audio_path, beam_size=5)
            
            # Collect all text segments
            transcript_text = ""
            for segment in segments:
                transcript_text += segment.text + " "
            
            # Create text file path (same directory as audio, but with .txt extension)
            base_path = os.path.splitext(audio_path)[0]
            text_path = f"{base_path}.txt"
            
            # Write transcript to file
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(transcript_text.strip())
            
            logger.info(f"Transcription completed: {text_path}")
            logger.info(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")
            
            return text_path
            
        except Exception as e:
            logger.error(f"Error transcribing audio file {audio_path}: {e}", exc_info=True)
            return None

    def transcribe_podcast(self, podcast_id: int, worker_id: Optional[str] = None) -> bool:
        """
        Transcribe a podcast audio file to text using checkout/checkin mechanism.
        
        Args:
            podcast_id: ID of the podcast to transcribe
            worker_id: Optional worker ID (uses instance worker_id if not provided)
            
        Returns:
            True if successful, False otherwise
        """
        if worker_id is None:
            worker_id = self.worker_id
            
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            # Checkout podcast with downloaded state
            podcast = checkout_manager.checkout_podcast(podcast_id, worker_id, PodcastStatus.downloaded)
            if not podcast:
                logger.debug(f"Could not checkout podcast {podcast_id} for transcription")
                return False

            logger.info(f"Transcribing podcast: {podcast.title} (checked out by {worker_id})")

            try:
                if not podcast.file_path or not os.path.exists(podcast.file_path):
                    error_msg = f"Audio file not found: {podcast.file_path}"
                    logger.error(error_msg)
                    checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, error_msg)
                    return False

                # Convert audio to text
                text_path = self.convert_to_text(podcast.file_path)
                
                if text_path and os.path.exists(text_path):
                    # Update podcast record fields
                    podcast.transcribed_text_path = text_path
                    podcast.error_message = None
                    
                    # Checkin with transcribed state
                    success = checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.transcribed)
                    if success:
                        logger.info(f"Successfully transcribed and checked in podcast: {podcast.title}")
                        return True
                    else:
                        logger.error(f"Failed to checkin podcast {podcast_id} after successful transcription")
                        return False
                else:
                    error_msg = "Failed to generate transcript file"
                    logger.error(error_msg)
                    checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, error_msg)
                    return False

            except Exception as e:
                error_msg = f"Error transcribing podcast: {str(e)}"
                logger.error(f"Error transcribing podcast {podcast_id}: {error_msg}", exc_info=True)
                checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, error_msg)
                return False

        except Exception as e:
            logger.error(f"Error in transcribe_podcast for ID {podcast_id}: {e}", exc_info=True)
            # Attempt to checkin with failed state if we have the worker_id
            if 'checkout_manager' in locals() and 'worker_id' in locals():
                checkout_manager.checkin_podcast(podcast_id, worker_id, PodcastStatus.failed, str(e))
            return False
        finally:
            db.close()

    def process_available_podcasts(self, limit: int = 5) -> dict:
        """
        Process available podcasts for transcription using checkout mechanism.
        
        Args:
            limit: Maximum number of podcasts to process
            
        Returns:
            Dictionary with processing statistics
        """
        db = SessionLocal()
        checkout_manager = CheckoutManager(db)
        
        try:
            # Find available podcasts for transcription
            available_podcasts = checkout_manager.find_available_podcasts(PodcastStatus.downloaded, limit)
            
            if not available_podcasts:
                logger.debug("No downloaded podcasts available for transcription")
                return {"transcribed": 0, "failed": 0, "total": 0}

            transcribed = 0
            failed = 0
            
            for podcast in available_podcasts:
                success = self.transcribe_podcast(podcast.id)
                if success:
                    transcribed += 1
                else:
                    failed += 1

            logger.info(f"Transcription batch complete: {transcribed} transcribed, {failed} failed out of {len(available_podcasts)} available")
            return {"transcribed": transcribed, "failed": failed, "total": len(available_podcasts)}

        except Exception as e:
            logger.error(f"Error in process_available_podcasts: {e}", exc_info=True)
            return {"transcribed": 0, "failed": 0, "total": 0}
        finally:
            db.close()

    def cleanup_model(self):
        """Clean up the loaded model to free memory."""
        if self.model is not None:
            del self.model
            self.model = None
            logger.info("Whisper model cleaned up")