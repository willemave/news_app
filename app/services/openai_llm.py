from pathlib import Path
from typing import BinaryIO

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.core.settings import get_settings

logger = get_logger(__name__)
settings = get_settings()


class OpenAITranscriptionService:
    """OpenAI service for audio transcription using Whisper API."""

    def __init__(self):
        openai_api_key = getattr(settings, "openai_api_key", None)
        if not openai_api_key:
            raise ValueError("OpenAI API key is required for transcription service")

        self.client = OpenAI(api_key=openai_api_key)
        self.model_name = "gpt-4o-transcribe"
        logger.info("Initialized OpenAI provider for transcription")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def transcribe_audio(self, audio_file_path: Path) -> tuple[str, str | None]:
        """Transcribe audio file using OpenAI Whisper API.

        Args:
            audio_file_path: Path to the audio file to transcribe

        Returns:
            Tuple of (transcript, language_code)
        """
        try:
            with open(audio_file_path, "rb") as audio_file:
                logger.info(f"Sending audio file to OpenAI for transcription: {audio_file_path}")

                transcription = self.client.audio.transcriptions.create(
                    model=self.model_name,
                    file=audio_file,
                    response_format="verbose_json",  # Get more details including language
                )

                transcript = transcription.text
                language = getattr(transcription, "language", None)

                logger.info(
                    f"Successfully transcribed audio. "
                    f"Length: {len(transcript)} chars, Language: {language}"
                )

                return transcript, language

        except Exception as e:
            logger.error(f"Error transcribing audio with OpenAI: {e}")
            raise

    def transcribe_audio_from_buffer(
        self, audio_buffer: BinaryIO, filename: str
    ) -> tuple[str, str | None]:
        """Transcribe audio from a file buffer using OpenAI Whisper API.

        Args:
            audio_buffer: File-like object containing audio data
            filename: Original filename for the audio

        Returns:
            Tuple of (transcript, language_code)
        """
        try:
            logger.info(f"Sending audio buffer to OpenAI for transcription: {filename}")

            # OpenAI client needs a filename for format detection
            audio_buffer.name = filename

            transcription = self.client.audio.transcriptions.create(
                model=self.model_name, file=audio_buffer, response_format="verbose_json"
            )

            transcript = transcription.text
            language = getattr(transcription, "language", None)

            logger.info(
                f"Successfully transcribed audio buffer. "
                f"Length: {len(transcript)} chars, Language: {language}"
            )

            return transcript, language

        except Exception as e:
            logger.error(f"Error transcribing audio buffer with OpenAI: {e}")
            raise


# Global instance
_openai_service = None


def get_openai_transcription_service() -> OpenAITranscriptionService:
    """Get the global OpenAI transcription service instance."""
    global _openai_service
    if _openai_service is None:
        _openai_service = OpenAITranscriptionService()
    return _openai_service
