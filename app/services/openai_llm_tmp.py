import contextlib
import json
import os
import re
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any, BinaryIO

from openai import OpenAI, OpenAIError
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import NewsSummary, StructuredSummary
from app.services.llm_prompts import generate_summary_prompt
from app.utils.error_logger import GenericErrorLogger
from app.utils.json_repair import strip_json_wrappers, try_repair_truncated_json

logger = get_logger(__name__)
settings = get_settings()
error_logger = GenericErrorLogger("openai_llm")

# Constants
MAX_FILE_SIZE_MB = 25
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_DURATION_SECONDS = 10 * 60  # 10 minutes in seconds
MAX_CONTENT_LENGTH = 1500000  # Maximum characters (~300K tokens, leaves room for prompt + output)


class StructuredSummaryRetryableError(Exception):
    """Retryable summarization failure used to trigger Tenacity retries."""



class OpenAISummarizationService:
    """OpenAI service for content summarization using GPT-5-mini."""

    def __init__(self):
        openai_api_key = getattr(settings, "openai_api_key", None)
        if not openai_api_key:
            raise ValueError("OpenAI API key is required for LLM service")

        self.client = OpenAI(api_key=openai_api_key)
        self.model_name = "gpt-5-mini"
        logger.info("Initialized OpenAI provider for summarization")

    @staticmethod
    def _extract_json_payload(validation_error: ValidationError) -> str | None:
        """Return the raw JSON payload embedded in a ValidationError, if available."""

        for error in validation_error.errors():
            input_value = error.get("input")
            if isinstance(input_value, str):
                return input_value
        return None

    def _parse_summary_payload(
        self,
        raw_payload: str,
        schema: type[StructuredSummary] | type[NewsSummary],
        content_id: str,
    ) -> StructuredSummary | NewsSummary | None:
        """Clean and parse an OpenAI JSON payload into the target schema."""

        cleaned_payload = strip_json_wrappers(raw_payload)
        if not cleaned_payload:
            logger.error("OpenAI response payload empty after cleanup")
            error = ValueError("Empty payload after cleanup")
            error_logger.log_processing_error(
                item_id=content_id or "unknown",
                error=error,
                operation="openai_empty_payload",
                context={"raw_payload": raw_payload, "response_length": len(raw_payload)},
            )
            return None

        try:
            summary_data: Any = json.loads(cleaned_payload)
        except json.JSONDecodeError as decode_error:
            repaired_payload = try_repair_truncated_json(cleaned_payload)
            if not repaired_payload:
                logger.error(
                    "Failed to repair truncated JSON from OpenAI response: %s", decode_error
                )
                error_logger.log_processing_error(
                    item_id=content_id or "unknown",
                    error=decode_error,
                    operation="openai_json_decode_error",
                    context={
                        "cleaned_payload": cleaned_payload,
                        "response_length": len(cleaned_payload),
                    },
                )
                return None

            logger.info("Repaired OpenAI JSON payload after initial decode failure")

            try:
                summary_data = json.loads(repaired_payload)
            except json.JSONDecodeError as repair_error:
                logger.error("Failed to decode repaired OpenAI JSON payload: %s", repair_error)
                error_logger.log_processing_error(
                    item_id=content_id or "unknown",
                    error=repair_error,
                    operation="openai_json_repair_failed",
                    context={
                        "repaired_payload": repaired_payload,
                        "response_length": len(repaired_payload),
                    },
                )
                return None

        try:
            return schema.model_validate(summary_data)
        except ValidationError as schema_error:
            recovered = self._attempt_structured_summary_recovery(
                summary_data,
                schema,
                content_id,
            )
            if recovered is not None:
                return recovered

            logger.error("OpenAI JSON payload failed schema validation: %s", schema_error)
            response_text = (
                json.dumps(summary_data, ensure_ascii=False)[:2000]
                if isinstance(summary_data, dict)
                else str(summary_data)[:2000]
            )
            error_logger.log_processing_error(
                item_id=content_id or "unknown",
                error=schema_error,
                operation="openai_schema_validation_error",
                context={"summary_data": response_text, "response_length": len(response_text)},
            )
            return None

    @staticmethod
    def _finalize_summary(
        summary: StructuredSummary | NewsSummary,
        content_type: str,
    ) -> StructuredSummary | NewsSummary:
        """Apply post-processing to the structured summary before returning it."""

        if content_type != "news_digest" and hasattr(summary, "quotes") and summary.quotes:
            filtered_quotes = [quote for quote in summary.quotes if len(quote.text or "") >= 10]
            if len(filtered_quotes) != len(summary.quotes):
                logger.warning("Filtered out quotes shorter than 10 characters")
                summary.quotes = filtered_quotes

        return summary

    @staticmethod
    def _attempt_structured_summary_recovery(
        summary_data: Any,
        schema: type[StructuredSummary] | type[NewsSummary],
        content_id: str,
    ) -> StructuredSummary | None:
        """Attempt to coerce partial payloads into a valid StructuredSummary."""

        if schema is not StructuredSummary or not isinstance(summary_data, dict):
            return None

        normalized = deepcopy(summary_data)

        # Always ensure classification defaults to to_read
        classification = normalized.get("classification")
        if not isinstance(classification, str) or not classification.strip():
            normalized["classification"] = "to_read"

        # Normalize bullet points: accept string lists or synthesize from overview/key points
        bullet_points: list[dict[str, str]] = []
        raw_bullets = normalized.get("bullet_points")

        if isinstance(raw_bullets, list):
            for entry in raw_bullets:
                if isinstance(entry, dict):
                    text = str(entry.get("text", "")).strip()
                    if not text:
                        continue
                    category = str(entry.get("category", "insight")).strip() or "insight"
                    bullet_points.append({"text": text, "category": category})
                elif isinstance(entry, str) and entry.strip():
                    bullet_points.append({"text": entry.strip(), "category": "insight"})

        if not bullet_points:
            key_points = normalized.get("key_points")
            if isinstance(key_points, list):
                bullet_points.extend(
                    {"text": item.strip(), "category": "insight"}
                    for item in key_points
                    if isinstance(item, str) and item.strip()
                )

        if not bullet_points:
            overview = normalized.get("overview")
            if isinstance(overview, str):
                overview_text = overview.strip()
                sentences = [
                    sentence.strip()
                    for sentence in re.split(r"(?<=[.!?])\s+", overview_text)
                    if sentence and len(sentence.strip()) >= 10
                ]
                if not sentences and len(overview_text) >= 10:
                    sentences = [overview_text[:400]]

                bullet_points.extend(
                    {"text": sentence[:400], "category": "insight"} for sentence in sentences[:3]
                )

        if not bullet_points:
            title = normalized.get("title")
            if isinstance(title, str):
                title_text = title.strip()
                if len(title_text) >= 10:
                    bullet_points.append({"text": title_text[:400], "category": "insight"})

        if not bullet_points:
            logger.error(
                "Unable to synthesize bullet points for content %s during recovery", content_id
            )
            return None

        # Ensure minimum bullet point count expected by schema (3)
        while len(bullet_points) < 3:
            bullet_points.append(dict(bullet_points[-1]))

        normalized["bullet_points"] = bullet_points[:50]

        # Normalize quotes to required shape
        quotes = []
        raw_quotes = normalized.get("quotes")
        if isinstance(raw_quotes, list):
            for item in raw_quotes:
                if isinstance(item, dict):
                    raw_text = str(item.get("text", "")).strip()
                    if not raw_text:
                        continue
                    context = (
                        str(item.get("context", "Source unspecified")).strip()
                        or "Source unspecified"
                    )
                    quotes.append({"text": raw_text, "context": context})
                elif isinstance(item, str) and item.strip():
                    quotes.append({"text": item.strip(), "context": "Source unspecified"})
        normalized["quotes"] = quotes[:50]

        # Topics should be a list of strings
        topics = normalized.get("topics")
        if isinstance(topics, list):
            normalized["topics"] = [str(topic).strip() for topic in topics if str(topic).strip()]
        else:
            normalized["topics"] = []

        # Ensure full_markdown field exists even if empty string
        if not isinstance(normalized.get("full_markdown"), str):
            normalized["full_markdown"] = ""

        # Remove helper fields not part of schema to avoid validation issues
        normalized.pop("key_points", None)

        try:
            recovered = StructuredSummary.model_validate(normalized)
        except ValidationError as recovery_error:
            logger.error(
                "Structured summary recovery failed for content %s: %s",
                content_id,
                recovery_error,
            )
            return None

        logger.info(
            "Recovered structured summary payload after schema failure for content %s",
            content_id,
        )
        return recovered

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def summarize_content(
        self,
        content: str,
        max_bullet_points: int = 6,
        max_quotes: int = 8,
        content_type: str = "article",
    ) -> StructuredSummary | NewsSummary | None:
        """Summarize content using LLM and classify it.

        Args:
            content: The content to summarize
            max_bullet_points: Maximum number of bullet points to generate (default: 6)
            max_quotes: Maximum number of quotes to extract (default: 8)
            content_type: Type of content - "article" or "podcast" (default: "article")

        Returns:
            StructuredSummary with bullet points, quotes, classification, and full_markdown
        """
        content_identifier = str(id(content))

        try:
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")

            if len(content) > MAX_CONTENT_LENGTH:
                logger.warning(
                    "Content length (%s chars) exceeds max (%s chars), truncating",
                    len(content),
                    MAX_CONTENT_LENGTH,
                )
                content = content[:MAX_CONTENT_LENGTH] + "\n\n[Content truncated due to length]"

            # Generate cache-optimized prompts (system instructions + user content)
            system_message, user_template = generate_summary_prompt(
                content_type, max_bullet_points, max_quotes
            )
            user_message = user_template.format(content=content)

            schema: type[StructuredSummary] | type[NewsSummary]
            schema = NewsSummary if content_type == "news_digest" else StructuredSummary

            max_output_tokens = 25000  # Large limit for full_markdown support
            if content_type == "podcast":
                max_output_tokens = 8000  # Podcasts don't include transcript in full_markdown
            elif content_type == "news_digest":
                max_output_tokens = 4000  # Increased to reduce truncation errors
            elif content_type == "hackernews":
                max_output_tokens = 30000  # Needs even more for article + comments

            try:
                response = self.client.responses.parse(
                    model=self.model_name,
                    input=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message},
                    ],
                    max_output_tokens=max_output_tokens,
                    text_format=schema,
                    prompt_cache_key=f"summary_{content_type}",  # Group by content type for caching
                )
            except ValidationError as validation_error:
                logger.warning("OpenAI structured output validation failed: %s", validation_error)
                raw_payload = self._extract_json_payload(validation_error) or ""

                # Try to repair truncated JSON before failing
                if "EOF while parsing" in str(validation_error) and raw_payload:
                    try:
                        repaired = try_repair_truncated_json(raw_payload)
                        if repaired:
                            logger.info("Attempting to use repaired JSON after truncation")
                            # Attempt to validate the repaired JSON
                            if content_type == "news_digest":
                                return NewsSummary.model_validate_json(repaired)
                            else:
                                return StructuredSummary.model_validate_json(repaired)
                    except Exception as repair_error:
                        logger.warning("JSON repair failed: %s", repair_error)

                error_logger.log_processing_error(
                    item_id=content_identifier or "unknown",
                    error=validation_error,
                    operation="openai_structured_output_error",
                    context={"raw_payload": raw_payload, "response_length": len(raw_payload)},
                )
                raise StructuredSummaryRetryableError(
                    "OpenAI structured output validation failed; retrying"
                ) from validation_error

            if not response.output:
                logger.error("LLM returned no choices")
                error_logger.log_processing_error(
                    item_id=content_identifier or "unknown",
                    error=ValueError("LLM returned no output"),
                    operation="openai_no_output",
                    context={},
                )
                return None

            parsed_message = response.output_parsed
            if parsed_message is None:
                logger.error("Parsed response missing from OpenAI response")
                output_text = getattr(response, "output_text", "")
                error_logger.log_processing_error(
                    item_id=content_identifier or "unknown",
                    error=ValueError("Parsed response missing"),
                    operation="openai_missing_parsed_message",
                    context={"output_text": output_text},
                )
                return None

            # Log cache metrics for monitoring
            usage = response.usage
            if usage:
                # OpenAI uses input_tokens for prompt tokens
                input_tokens = getattr(usage, "input_tokens", 0)

                # Access cached tokens from input_tokens_details if available
                cached_tokens = 0
                if hasattr(usage, "input_tokens_details") and usage.input_tokens_details:
                    cached_tokens = getattr(usage.input_tokens_details, "cached_tokens", 0)

                cache_hit_rate = (cached_tokens / input_tokens * 100) if input_tokens > 0 else 0

                logger.info(
                    "OpenAI cache metrics - content_type: %s, input_tokens: %d, cached_tokens: %d, cache_hit_rate: %.1f%%",
                    content_type,
                    input_tokens,
                    cached_tokens,
                    cache_hit_rate,
                )

            return self._finalize_summary(parsed_message, content_type)

        except StructuredSummaryRetryableError as retryable_error:
            logger.warning("Retryable structured summary failure: %s", retryable_error)
            raise
        except OpenAIError as error:
            logger.error("OpenAI structured output error: %s", error)
            error_logger.log_processing_error(
                item_id=content_identifier or "unknown",
                error=error,
                operation="openai_structured_output_error",
                context={},
            )
            return None
        except Exception as error:  # noqa: BLE001
            logger.error("Error generating structured summary: %s", error)
            error_logger.log_processing_error(
                item_id=content_identifier or "unknown",
                error=error,
                operation="unexpected_error",
                context={},
            )
            return None


class OpenAITranscriptionService:
    """OpenAI service for audio transcription using Whisper API."""

    def __init__(self):
        openai_api_key = getattr(settings, "openai_api_key", None)
        if not openai_api_key:
            raise ValueError("OpenAI API key is required for transcription service")

        self.client = OpenAI(api_key=openai_api_key)
        self.model_name = "gpt-4o-transcribe"
        logger.info("Initialized OpenAI provider for transcription")

    def _get_audio_format(self, file_path: Path) -> str:
        """Determine audio format from file extension."""
        extension = file_path.suffix.lower()
        format_map = {
            ".mp3": "mp3",
            ".mp4": "mp4",
            ".m4a": "mp4",
            ".wav": "wav",
            ".webm": "webm",
            ".ogg": "ogg",
            ".opus": "opus",
            ".flac": "flac",
        }
        return format_map.get(extension, "mp3")

    def _check_file_size(self, file_path: Path) -> bool:
        """Check if file is within size limit."""
        file_size = os.path.getsize(file_path)
        return file_size <= MAX_FILE_SIZE_BYTES

    def _get_audio_duration(self, file_path: Path) -> float:
        """Get audio duration in seconds using ffprobe."""
        try:
            cmd = [
                "ffprobe",
                "-i",
                str(file_path),
                "-show_entries",
                "format=duration",
                "-v",
                "quiet",
                "-of",
                "csv=p=0",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return float(result.stdout.strip())
        except (subprocess.CalledProcessError, ValueError) as e:
            logger.error(f"Failed to get audio duration: {e}")
            # Estimate based on file size - rough approximation
            # Assuming 128kbps bitrate as average
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            estimated_duration = file_size_mb * 60  # Very rough estimate
            logger.warning(f"Using estimated duration: {estimated_duration:.1f} seconds")
            return estimated_duration

    def _split_audio_file_ffmpeg(self, file_path: Path) -> list[Path]:
        """Split large audio file into chunks using ffmpeg directly."""
        logger.info(f"Splitting large audio file using ffmpeg: {file_path}")

        # Get audio duration
        duration = self._get_audio_duration(file_path)
        num_chunks = int((duration + CHUNK_DURATION_SECONDS - 1) // CHUNK_DURATION_SECONDS)

        logger.info(f"Audio duration: {duration:.1f}s, will split into {num_chunks} chunks")

        # Create temporary directory for chunks
        temp_dir = Path(tempfile.mkdtemp(prefix="audio_chunks_"))
        chunk_paths = []
        audio_format = self._get_audio_format(file_path)

        try:
            for i in range(num_chunks):
                start_time = i * CHUNK_DURATION_SECONDS

                # Create chunk filename
                chunk_filename = f"chunk_{i:03d}.{audio_format}"
                chunk_path = temp_dir / chunk_filename

                # Build ffmpeg command
                cmd = [
                    "ffmpeg",
                    "-i",
                    str(file_path),
                    "-ss",
                    str(start_time),
                    "-t",
                    str(CHUNK_DURATION_SECONDS),
                    "-acodec",
                    "copy",  # Copy codec to avoid re-encoding
                    "-y",  # Overwrite output file
                    str(chunk_path),
                ]

                logger.info(f"Creating chunk {i + 1}/{num_chunks}")

                # Execute ffmpeg
                result = subprocess.run(cmd, capture_output=True, text=True)

                if result.returncode != 0:
                    raise RuntimeError(f"ffmpeg failed: {result.stderr}")

                chunk_paths.append(chunk_path)

                # Verify chunk was created
                if not chunk_path.exists() or os.path.getsize(chunk_path) == 0:
                    raise RuntimeError(f"Failed to create chunk: {chunk_path}")

                logger.info(
                    f"Created chunk {i + 1}/{num_chunks}: "
                    f"{os.path.getsize(chunk_path) / (1024 * 1024):.1f}MB"
                )

            return chunk_paths

        except Exception as e:
            # Clean up on error
            for chunk_path in chunk_paths:
                if chunk_path.exists():
                    chunk_path.unlink()
            if temp_dir.exists():
                temp_dir.rmdir()
            raise e

    def _check_ffmpeg_available(self) -> bool:
        """Check if ffmpeg is available on the system."""
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False

    def _get_transcription_prompt(self, file_path: Path) -> str:
        """Generate a contextual prompt based on the file name and podcast context."""
        file_name = file_path.stem

        # Default prompt for podcasts
        prompt = (
            "This is a podcast episode. Please transcribe accurately, "
            "including speaker names when mentioned."
        )

        # Add specific context based on filename patterns
        if "interview" in file_name.lower():
            prompt = (
                "This is a podcast interview. Please transcribe accurately, "
                "noting different speakers."
            )
        elif "tech" in file_name.lower() or "ai" in file_name.lower():
            prompt = (
                "This is a technology podcast discussing AI, software, and tech innovations. "
                "Include technical terms accurately."
            )
        elif "news" in file_name.lower():
            prompt = (
                "This is a news podcast. Please transcribe accurately, "
                "including proper names and places."
            )
        elif any(term in file_name.lower() for term in ["bg2", "bill", "gurley", "gerstner"]):
            prompt = (
                "This is the BG2 podcast with Bill Gurley and Brad Gerstner discussing "
                "technology, venture capital, and market trends."
            )

        return prompt

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    def _transcribe_single_file(self, file_path: Path, prompt: str) -> tuple[str, str | None]:
        """Transcribe a single audio file."""
        with open(file_path, "rb") as audio_file:
            logger.info(f"Sending audio file to OpenAI for transcription: {file_path}")

            transcription = self.client.audio.transcriptions.create(
                model=self.model_name, file=audio_file, response_format="json", prompt=prompt
            )

            transcript = transcription.text
            language = getattr(transcription, "language", None)

            logger.info(
                f"Successfully transcribed audio. "
                f"Length: {len(transcript)} chars, Language: {language}"
            )

            return transcript, language

    def transcribe_audio(self, audio_file_path: Path) -> tuple[str, str | None]:
        """Transcribe audio file using OpenAI Whisper API.

        Handles large files by splitting them into chunks.

        Args:
            audio_file_path: Path to the audio file to transcribe

        Returns:
            Tuple of (transcript, language_code)
        """
        try:
            # Generate contextual prompt
            prompt = self._get_transcription_prompt(audio_file_path)
            logger.info(f"Using transcription prompt: {prompt}")

            # Check file size
            if self._check_file_size(audio_file_path):
                # File is small enough, transcribe directly
                return self._transcribe_single_file(audio_file_path, prompt)

            # File is too large, need to split
            logger.info(f"File exceeds {MAX_FILE_SIZE_MB}MB limit, splitting into chunks")

            # Check if ffmpeg is available
            if not self._check_ffmpeg_available():
                raise RuntimeError(
                    "Audio file exceeds 25MB limit but ffmpeg is not available for splitting. "
                    "Please install ffmpeg (e.g., 'brew install ffmpeg' on macOS) "
                    "or use audio files smaller than 25MB."
                )

            # Split using ffmpeg
            chunk_paths = self._split_audio_file_ffmpeg(audio_file_path)

            try:
                # Transcribe each chunk
                transcripts = []
                detected_language = None

                for i, chunk_path in enumerate(chunk_paths):
                    logger.info(f"Transcribing chunk {i + 1}/{len(chunk_paths)}")

                    # Adjust prompt for subsequent chunks
                    chunk_prompt = prompt
                    if i > 0:
                        chunk_prompt += " This is a continuation of the previous segment."

                    chunk_transcript, chunk_language = self._transcribe_single_file(
                        chunk_path, chunk_prompt
                    )

                    transcripts.append(chunk_transcript)

                    # Use the language from the first chunk
                    if detected_language is None and chunk_language:
                        detected_language = chunk_language

                # Combine transcripts
                full_transcript = " ".join(transcripts)

                logger.info(
                    f"Successfully transcribed {len(chunk_paths)} chunks. "
                    f"Total length: {len(full_transcript)} chars"
                )

                return full_transcript, detected_language

            finally:
                # Clean up chunk files
                for chunk_path in chunk_paths:
                    if chunk_path.exists():
                        chunk_path.unlink()

                # Remove temporary directory
                if chunk_paths:
                    temp_dir = chunk_paths[0].parent
                    if temp_dir.exists() and temp_dir.name.startswith("audio_chunks_"):
                        with contextlib.suppress(OSError):
                            temp_dir.rmdir()

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
            # For buffers, we need to save to a temporary file to check size and potentially split
            with tempfile.NamedTemporaryFile(
                suffix=Path(filename).suffix, delete=False
            ) as tmp_file:
                tmp_file.write(audio_buffer.read())
                tmp_path = Path(tmp_file.name)

            try:
                # Use the file-based method
                return self.transcribe_audio(tmp_path)
            finally:
                # Clean up temporary file
                if tmp_path.exists():
                    tmp_path.unlink()

        except Exception as e:
            logger.error(f"Error transcribing audio buffer with OpenAI: {e}")
            raise


# Global instances
_openai_transcription_service = None
_openai_summarization_service = None


def get_openai_transcription_service() -> OpenAITranscriptionService:
    """Get the global OpenAI transcription service instance."""
    global _openai_transcription_service
    if _openai_transcription_service is None:
        _openai_transcription_service = OpenAITranscriptionService()
    return _openai_transcription_service


def get_openai_summarization_service() -> OpenAISummarizationService:
    """Get the global OpenAI summarization service instance."""
    global _openai_summarization_service
    if _openai_summarization_service is None:
        _openai_summarization_service = OpenAISummarizationService()
    return _openai_summarization_service
