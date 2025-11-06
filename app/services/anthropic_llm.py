"""
Anthropic LLM service for content summarization.
Matches the OpenAI service interface for easy comparison and potential replacement.
"""

import json

from anthropic import Anthropic, AnthropicError
from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import NewsSummary, StructuredSummary
from app.services.llm_prompts import generate_summary_prompt
from app.utils.error_logger import GenericErrorLogger
from app.utils.json_repair import try_repair_truncated_json

logger = get_logger(__name__)
settings = get_settings()
error_logger = GenericErrorLogger("anthropic_llm")

# Constants
MAX_CONTENT_LENGTH = 1500000  # Maximum characters (~300K tokens, leaves room for prompt + output)


class StructuredSummaryRetryableError(Exception):
    """Retryable summarization failure used to trigger Tenacity retries."""


class AnthropicSummarizationService:
    """Anthropic-powered summarization service matching OpenAI interface."""

    def __init__(self):
        anthropic_api_key = getattr(settings, "anthropic_api_key", None)
        if not anthropic_api_key:
            raise ValueError("Anthropic API key is required for LLM service")

        # Set longer timeout for large content (30 minutes)
        self.client = Anthropic(api_key=anthropic_api_key, timeout=1800.0)
        self.model_name = "claude-haiku-4-5-20251001"
        logger.info("Initialized Anthropic provider for summarization")

    @staticmethod
    def _extract_json_from_response(content: str) -> str:
        """Extract JSON from response, handling markdown code blocks."""
        # Remove markdown code blocks if present
        if "```json" in content:
            start = content.find("```json") + 7
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()
        elif "```" in content:
            start = content.find("```") + 3
            end = content.find("```", start)
            if end != -1:
                content = content[start:end].strip()

        return content.strip()

    def _parse_summary_payload(
        self,
        raw_payload: str,
        schema: type[StructuredSummary] | type[NewsSummary],
    ) -> StructuredSummary | NewsSummary | None:
        """Parse and validate summary payload from raw JSON string."""
        try:
            # Clean up the payload
            cleaned_payload = self._extract_json_from_response(raw_payload)

            # Try to parse as JSON
            try:
                data = json.loads(cleaned_payload)
            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error: {e}, attempting repair")
                # Try to repair truncated JSON
                repaired = try_repair_truncated_json(cleaned_payload)
                if repaired:
                    data = json.loads(repaired)
                else:
                    raise

            # Validate with Pydantic
            return schema.model_validate(data)

        except Exception as e:
            logger.error(f"Failed to parse summary payload: {e}")
            error_logger.log_processing_error(
                item_id="unknown",
                error=e,
                operation="anthropic_parse_summary",
                context={"raw_payload": raw_payload[:500]},
            )
            return None

    @staticmethod
    def _finalize_summary(
        summary: StructuredSummary | NewsSummary,
        content_type: str,
    ) -> StructuredSummary | NewsSummary:
        """Apply final tweaks to summary before returning."""
        # For news digest, ensure we have the summary_type field
        if isinstance(summary, NewsSummary):
            return summary

        # For structured summaries, ensure classification is set
        if isinstance(summary, StructuredSummary) and not summary.classification:
            summary.classification = "to_read"

        return summary

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        retry_error_callback=lambda retry_state: None,
    )
    def summarize_content(
        self,
        content: str,
        max_bullet_points: int = 6,
        max_quotes: int = 8,
        content_type: str = "article",
    ) -> StructuredSummary | NewsSummary | None:
        """Summarize content using Anthropic Claude and classify it.

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

            # Use the shared prompt generation for consistency
            system_message, user_template = generate_summary_prompt(
                content_type, max_bullet_points, max_quotes
            )
            user_message = user_template.format(content=content)

            schema: type[StructuredSummary] | type[NewsSummary]
            schema = NewsSummary if content_type == "news_digest" else StructuredSummary

            # Determine max tokens based on content type
            max_output_tokens = 25000  # Large limit for full_markdown support
            if content_type == "podcast":
                max_output_tokens = 8000  # Podcasts don't include transcript in full_markdown
            elif content_type == "news_digest":
                max_output_tokens = 4000  # Increased to reduce truncation errors
            elif content_type == "hackernews":
                max_output_tokens = 30000  # Needs even more for article + comments

            # Create the schema description for Claude
            schema_json = schema.model_json_schema()
            schema_description = json.dumps(schema_json, indent=2)

            # Combine system message with schema instructions
            combined_system = f"""{system_message}

You must respond with valid JSON that matches this schema exactly:

{schema_description}

Important:
- Return ONLY valid JSON, no markdown code blocks or additional text
- Ensure all required fields are present
- Follow the schema structure precisely"""

            try:
                # Use streaming to avoid timeout issues with large content
                response_text = ""
                response_usage = None

                with self.client.messages.stream(
                    model=self.model_name,
                    max_tokens=max_output_tokens,
                    system=combined_system,
                    messages=[
                        {
                            "role": "user",
                            "content": user_message,
                        }
                    ],
                ) as stream:
                    # Collect all text chunks
                    for text in stream.text_stream:
                        response_text += text

                    # Get the final message for usage stats
                    final_message = stream.get_final_message()
                    response_usage = (
                        final_message.usage if hasattr(final_message, "usage") else None
                    )
            except ValidationError as validation_error:
                logger.warning("Anthropic validation failed: %s", validation_error)
                raise StructuredSummaryRetryableError(
                    "Anthropic validation failed; retrying"
                ) from validation_error

            if not response_text:
                logger.error("Anthropic returned no content")
                error_logger.log_processing_error(
                    item_id=content_identifier or "unknown",
                    error=ValueError("Anthropic returned no content"),
                    operation="anthropic_no_output",
                    context={},
                )
                return None

            # Parse the response
            parsed_summary = self._parse_summary_payload(response_text, schema)
            if parsed_summary is None:
                logger.error("Failed to parse Anthropic response")
                return None

            # Log usage metrics if available (Anthropic also provides cache metrics)
            if response_usage:
                input_tokens = getattr(response_usage, "input_tokens", 0)
                cache_read_tokens = getattr(response_usage, "cache_read_input_tokens", 0)
                cache_hit_rate = (cache_read_tokens / input_tokens * 100) if input_tokens > 0 else 0

                logger.info(
                    "Anthropic usage metrics - content_type: %s, input_tokens: %d, "
                    "cache_read_tokens: %d, cache_hit_rate: %.1f%%",
                    content_type,
                    input_tokens,
                    cache_read_tokens,
                    cache_hit_rate,
                )

            return self._finalize_summary(parsed_summary, content_type)

        except StructuredSummaryRetryableError as retryable_error:
            logger.warning("Retryable structured summary failure: %s", retryable_error)
            raise
        except AnthropicError as error:
            logger.error("Anthropic API error: %s", error)
            error_logger.log_processing_error(
                item_id=content_identifier or "unknown",
                error=error,
                operation="anthropic_api_error",
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


def get_anthropic_summarization_service() -> AnthropicSummarizationService:
    """Get Anthropic summarization service instance."""
    return AnthropicSummarizationService()
