import os
from datetime import datetime
from typing import Optional
from faster_whisper import WhisperModel
from app.database import SessionLocal
from app.models import Podcasts, PodcastStatus
from app.config import logger

class PodcastConverter:
    def __init__(self, model_size: str = "base"):
        """
        Initialize the podcast converter with a Whisper model.
        
        Args:
            model_size: Size of the Whisper model to use (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self.model = None
        
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

    async def transcribe_podcast(self, podcast_id: int) -> bool:
        """
        Transcribe a podcast audio file to text.
        
        Args:
            podcast_id: ID of the podcast to transcribe
            
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

            if podcast.status != PodcastStatus.downloaded:
                logger.warning(f"Podcast {podcast_id} is not in downloaded status (current: {podcast.status})")
                return False

            if not podcast.file_path or not os.path.exists(podcast.file_path):
                error_msg = f"Audio file not found: {podcast.file_path}"
                logger.error(error_msg)
                podcast.status = PodcastStatus.failed
                podcast.error_message = error_msg
                db.commit()
                return False

            logger.info(f"Transcribing podcast: {podcast.title}")

            # Convert audio to text
            text_path = self.convert_to_text(podcast.file_path)
            
            if text_path and os.path.exists(text_path):
                # Update podcast record
                podcast.transcribed_text_path = text_path
                podcast.status = PodcastStatus.transcribed
                podcast.error_message = None
                db.commit()
                
                logger.info(f"Successfully transcribed podcast: {podcast.title}")
                return True
            else:
                error_msg = "Failed to generate transcript file"
                logger.error(error_msg)
                podcast.status = PodcastStatus.failed
                podcast.error_message = error_msg
                db.commit()
                return False

        except Exception as e:
            error_msg = f"Error in transcribe_podcast for ID {podcast_id}: {str(e)}"
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
                
            return False
        finally:
            db.close()

    async def transcribe_all_downloaded_podcasts(self) -> dict:
        """
        Transcribe all podcasts with status 'downloaded'.
        
        Returns:
            Dictionary with transcription statistics
        """
        db = SessionLocal()
        try:
            downloaded_podcasts = db.query(Podcasts).filter(
                Podcasts.status == PodcastStatus.downloaded
            ).all()
            
            if not downloaded_podcasts:
                logger.info("No downloaded podcasts to transcribe")
                return {"transcribed": 0, "failed": 0, "total": 0}

            transcribed = 0
            failed = 0
            
            for podcast in downloaded_podcasts:
                success = await self.transcribe_podcast(podcast.id)
                if success:
                    transcribed += 1
                else:
                    failed += 1

            logger.info(f"Transcription batch complete: {transcribed} transcribed, {failed} failed")
            return {"transcribed": transcribed, "failed": failed, "total": len(downloaded_podcasts)}

        except Exception as e:
            logger.error(f"Error in transcribe_all_downloaded_podcasts: {e}", exc_info=True)
            return {"transcribed": 0, "failed": 0, "total": 0}
        finally:
            db.close()

    def cleanup_model(self):
        """Clean up the loaded model to free memory."""
        if self.model is not None:
            del self.model
            self.model = None
            logger.info("Whisper model cleaned up")