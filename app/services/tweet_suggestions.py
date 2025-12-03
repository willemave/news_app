"""
Tweet suggestions service using Gemini via pydantic-ai.
Generates tweet suggestions for content items.
"""

import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator
from pydantic_ai import Agent, ModelRetry
from pydantic_ai.settings import ModelSettings
from tenacity import RetryCallState, retry, stop_after_attempt, wait_exponential

from app.constants import TWEET_SUGGESTION_MODEL
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.models.metadata import ContentData, ContentType
from app.services.llm_agents import get_basic_agent
from app.services.llm_prompts import get_tweet_generation_prompt
from app.utils.error_logger import GenericErrorLogger
from app.utils.json_repair import try_repair_truncated_json

logger = get_logger(__name__)
settings = get_settings()
error_logger = GenericErrorLogger("tweet_suggestions")

# Model for tweet generation
TWEET_MODEL = TWEET_SUGGESTION_MODEL
# Allow tweet suggestions for every content type (article, news, podcast, etc.).
SUPPORTED_CONTENT_TYPES = set(ContentType)


class TweetSuggestionLLM(BaseModel):
    """Structured tweet suggestion returned by the LLM."""

    id: int = Field(..., ge=1, le=3)
    text: str = Field(..., min_length=1)
    style_label: str | None = Field(default=None)


class TweetSuggestionsPayload(BaseModel):
    """Structured payload returned by the LLM."""

    suggestions: list[TweetSuggestionLLM] = Field(
        ..., min_length=3, max_length=3, description="Exactly three tweet suggestions"
    )

    @model_validator(mode="after")
    def ensure_three_suggestions(self) -> "TweetSuggestionsPayload":
        """Ensure exactly three suggestions are returned."""
        if len(self.suggestions) != 3:
            raise ValueError(f"Expected 3 suggestions, got {len(self.suggestions)}")
        return self


@dataclass
class TweetSuggestionData:
    """Internal data structure for a single tweet suggestion."""

    id: int
    text: str
    style_label: str | None


@dataclass
class TweetSuggestionsResult:
    """Result from tweet suggestion generation."""

    content_id: int
    creativity: int
    model: str
    suggestions: list[TweetSuggestionData]


def creativity_to_temperature(creativity: int) -> float:
    """
    Map creativity level (1-10) to temperature for LLM.

    Args:
        creativity: Integer 1-10

    Returns:
        Float temperature value (0.1 to 1.0)
    """
    # Clamp to valid range
    creativity = max(1, min(10, creativity))
    # Linear mapping: 1 -> 0.1, 10 -> 1.0
    return 0.1 + (creativity - 1) * 0.1


def _extract_content_context(content: ContentData) -> dict[str, str]:
    """
    Extract relevant context from ContentData for tweet generation.

    Args:
        content: The ContentData object

    Returns:
        Dictionary with title, source, platform, url, summary, key_points,
        quotes, questions, counter_arguments
    """
    title = content.display_title
    source = content.source or "Unknown"
    platform = content.platform or "web"

    # Get URL
    url = str(content.url)
    if content.content_type == ContentType.ARTICLE:
        # Prefer final URL after redirects for articles
        final_url = content.metadata.get("final_url_after_redirects")
        if final_url:
            url = final_url
    elif content.content_type == ContentType.NEWS:
        # For news, prefer the article URL from summary or metadata
        summary_data = content.metadata.get("summary")
        if isinstance(summary_data, dict):
            article_url = summary_data.get("article_url")
            if article_url:
                url = article_url
        # Fallback to article metadata
        article_meta = content.metadata.get("article")
        if isinstance(article_meta, dict):
            article_url = article_meta.get("url")
            if article_url:
                url = str(article_url)

    # Get summary text
    summary = ""
    key_points: list[str] = []
    quotes: list[str] = []
    questions: list[str] = []
    counter_arguments: list[str] = []

    summary_data = content.metadata.get("summary")
    if isinstance(summary_data, dict):
        # Check if it's a StructuredSummary or NewsSummary
        if "overview" in summary_data:
            summary = summary_data.get("overview", "")
        elif "summary" in summary_data:
            summary = summary_data.get("summary", "")

        # Get bullet points / key points
        bullet_points = summary_data.get("bullet_points", [])
        if bullet_points:
            # Handle both dict and string formats
            for point in bullet_points[:5]:  # Limit to 5 points
                if isinstance(point, dict):
                    key_points.append(point.get("text", ""))
                elif isinstance(point, str):
                    key_points.append(point)

        # Get quotes (for articles with StructuredSummary)
        raw_quotes = summary_data.get("quotes", [])
        if raw_quotes:
            for quote in raw_quotes[:3]:  # Limit to 3 quotes
                if isinstance(quote, dict):
                    quote_text = quote.get("text", "")
                    if quote_text:
                        quotes.append(quote_text)
                elif isinstance(quote, str):
                    quotes.append(quote)

        # Get questions
        raw_questions = summary_data.get("questions", [])
        if raw_questions:
            for q in raw_questions[:3]:  # Limit to 3 questions
                if isinstance(q, str):
                    questions.append(q)

        # Get counter-arguments
        raw_counter_args = summary_data.get("counter_arguments", [])
        if raw_counter_args:
            for arg in raw_counter_args[:3]:  # Limit to 3 counter-arguments
                if isinstance(arg, str):
                    counter_arguments.append(arg)

    # Fallback to short_summary if no overview
    if not summary:
        summary = content.short_summary or content.summary or ""

    return {
        "title": title,
        "source": source,
        "platform": platform,
        "url": url,
        "summary": summary,
        "key_points": "\n".join(f"- {p}" for p in key_points) if key_points else "N/A",
        "quotes": "\n".join(f'- "{q}"' for q in quotes) if quotes else "N/A",
        "questions": "\n".join(f"- {q}" for q in questions) if questions else "N/A",
        "counter_arguments": (
            "\n".join(f"- {arg}" for arg in counter_arguments) if counter_arguments else "N/A"
        ),
    }


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


def _parse_suggestions_response(raw_response: str) -> list[dict[str, Any]] | None:
    """
    Parse the LLM response into suggestion dictionaries.

    Args:
        raw_response: Raw string response from LLM

    Returns:
        List of suggestion dicts or None if parsing fails
    """
    try:
        cleaned = _extract_json_from_response(raw_response)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Try to repair truncated JSON
            repaired = try_repair_truncated_json(cleaned)
            if repaired:
                data = json.loads(repaired)
            else:
                logger.warning("Could not parse tweet suggestions JSON: %s", exc)
                return None

        # Extract suggestions array
        suggestions = data.get("suggestions", [])
        if not isinstance(suggestions, list) or len(suggestions) != 3:
            logger.warning("Expected exactly 3 suggestions, got %d", len(suggestions))
            return None

        return suggestions

    except Exception as e:
        logger.error("Failed to parse tweet suggestions: %s", e)
        error_logger.log_processing_error(
            item_id="unknown",
            error=e,
            operation="parse_tweet_suggestions",
            context={"raw_response": raw_response[:500]},
        )
        return None


def _validate_and_truncate_tweets(
    suggestions: list[dict[str, Any]],
) -> list[TweetSuggestionData]:
    """
    Validate suggestions and truncate if over 400 chars.

    Args:
        suggestions: List of suggestion dicts from LLM

    Returns:
        List of validated TweetSuggestionData
    """
    result = []
    for i, suggestion in enumerate(suggestions, start=1):
        text = suggestion.get("text", "")
        style_label = suggestion.get("style_label")

        # Truncate if too long (400 char limit for longer-form tweets)
        if len(text) > 400:
            logger.warning("Tweet %d exceeds 400 chars (%d), truncating", i, len(text))
            text = text[:397] + "..."

        result.append(
            TweetSuggestionData(
                id=suggestion.get("id", i),
                text=text,
                style_label=style_label,
            )
        )

    return result


def _log_generation_failure(retry_state: RetryCallState) -> None:
    """Log final generation failure after all retries."""
    content = retry_state.args[1] if len(retry_state.args) > 1 else None
    content_id = getattr(content, "id", "unknown")
    creativity = None
    if retry_state.kwargs:
        creativity = retry_state.kwargs.get("creativity")
    elif len(retry_state.args) > 3:
        creativity = retry_state.args[3]

    error = retry_state.outcome.exception() if retry_state.outcome else None
    logger.error(
        "Tweet generation failed after %d attempts | content_id=%s error=%s",
        retry_state.attempt_number,
        content_id,
        error,
    )
    if error:
        error_logger.log_processing_error(
            item_id=str(content_id),
            error=error,
            operation="tweet_generation_failure",
            context={"creativity": creativity},
        )
    return None


class TweetSuggestionService:
    """Service for generating tweet suggestions using Gemini."""

    def __init__(self):
        google_api_key = getattr(settings, "google_api_key", None)
        if not google_api_key:
            raise ValueError("Google API key is required for tweet suggestions")

        self.model_name = TWEET_MODEL
        logger.info("Initialized TweetSuggestionService with model %s", self.model_name)

    def _build_agent(self, system_prompt: str) -> Agent[None, TweetSuggestionsPayload]:
        """Create a configured pydantic-ai agent for tweet suggestions."""
        return get_basic_agent(
            model_spec=self.model_name,
            output_type=TweetSuggestionsPayload,
            system_prompt=system_prompt,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry_error_callback=_log_generation_failure,
    )
    def generate_suggestions(
        self,
        content: ContentData,
        message: str | None = None,
        creativity: int = 5,
    ) -> TweetSuggestionsResult | None:
        """
        Generate tweet suggestions for content.

        Args:
            content: The ContentData to generate tweets for.
            message: Optional user guidance/tweak message.
            creativity: Creativity level 1-10.

        Returns:
            TweetSuggestionsResult with 3 suggestions, or None on failure.
        """
        content_id = content.id or 0

        try:
            # Extract context from content
            context = _extract_content_context(content)

            # Get prompts
            system_message, user_template = get_tweet_generation_prompt(
                creativity=creativity,
                user_message=message,
            )

            # Format user message with content context
            user_message = user_template.format(**context)

            # Calculate temperature from creativity
            temperature = creativity_to_temperature(creativity)

            # Run Gemini via pydantic-ai
            agent = self._build_agent(system_prompt=system_message)
            run_result = agent.run_sync(
                user_message,
                model_settings=ModelSettings(
                    max_tokens=2000,
                    temperature=temperature,
                ),
            )

            payload = run_result.output

            # Validate and truncate
            suggestions = _validate_and_truncate_tweets(
                [suggestion.model_dump() for suggestion in payload.suggestions]
            )
            if len(suggestions) != 3:
                raise ValueError(f"Expected 3 suggestions after validation, got {len(suggestions)}")

            # Log usage metrics
            usage = run_result.usage()
            if usage:
                logger.info(
                    "Tweet generation - content_id: %d, creativity: %d, "
                    "input_tokens: %d, output_tokens: %d",
                    content_id,
                    creativity,
                    usage.input_tokens,
                    usage.output_tokens,
                )

            return TweetSuggestionsResult(
                content_id=content_id,
                creativity=creativity,
                model=self.model_name,
                suggestions=suggestions,
            )

        except (ModelRetry, ValidationError, ValueError) as e:
            logger.warning(
                "Gemini validation error generating tweets | content_id=%s error=%s",
                content_id,
                e,
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error generating tweets with Gemini | content_id=%s error=%s",
                content_id,
                e,
            )
            raise


# Module-level service instance (lazy initialization)
_service_instance: TweetSuggestionService | None = None


def get_tweet_suggestion_service() -> TweetSuggestionService:
    """Get or create the TweetSuggestionService singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = TweetSuggestionService()
    return _service_instance


def generate_tweet_suggestions(
    content: ContentData,
    message: str | None = None,
    creativity: int = 5,
) -> TweetSuggestionsResult | None:
    """
    Convenience function to generate tweet suggestions.

    Args:
        content: The ContentData to generate tweets for
        message: Optional user guidance/tweak message
        creativity: Creativity level 1-10

    Returns:
        TweetSuggestionsResult with 3 suggestions, or None on failure
    """
    service = get_tweet_suggestion_service()
    return service.generate_suggestions(content, message, creativity)
