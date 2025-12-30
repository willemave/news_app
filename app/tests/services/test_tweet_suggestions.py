"""Tests for tweet suggestions service."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.constants import TWEET_MODELS
from app.core.settings import get_settings
from app.models.metadata import ContentData, ContentStatus, ContentType
from app.services.llm_prompts import (
    creativity_to_style_hints,
    get_tweet_generation_prompt,
    length_to_char_range,
)
from app.services.tweet_suggestions import (
    TWEET_MODEL,
    TweetSuggestionService,
    TweetSuggestionLLM,
    TweetSuggestionsPayload,
    _extract_content_context,
    _parse_suggestions_response,
    _validate_and_truncate_tweets,
    creativity_to_temperature,
)

settings = get_settings()


class TestCreativityMapping:
    """Tests for creativity to temperature/style mapping."""

    def test_creativity_to_temperature_low(self) -> None:
        """Low creativity maps to low temperature."""
        assert creativity_to_temperature(1) == pytest.approx(0.1)
        assert creativity_to_temperature(2) == pytest.approx(0.2)
        assert creativity_to_temperature(3) == pytest.approx(0.3)

    def test_creativity_to_temperature_mid(self) -> None:
        """Mid creativity maps to mid temperature."""
        assert creativity_to_temperature(5) == pytest.approx(0.5)
        assert creativity_to_temperature(7) == pytest.approx(0.7)

    def test_creativity_to_temperature_high(self) -> None:
        """High creativity maps to high temperature."""
        assert creativity_to_temperature(9) == pytest.approx(0.9)
        assert creativity_to_temperature(10) == pytest.approx(1.0)

    def test_creativity_to_temperature_clamped(self) -> None:
        """Out of range values are clamped."""
        assert creativity_to_temperature(0) == pytest.approx(0.1)  # Clamped to 1
        assert creativity_to_temperature(15) == pytest.approx(1.0)  # Clamped to 10

    def test_creativity_to_style_hints_low(self) -> None:
        """Low creativity gets factual journalist style hints."""
        for creativity in [1, 2, 3]:
            hints = creativity_to_style_hints(creativity)
            assert "journalist" in hints.lower()
            assert "no emojis" in hints.lower()

    def test_creativity_to_style_hints_mid(self) -> None:
        """Mid creativity gets thoughtful commentator style hints."""
        for creativity in [4, 5, 6, 7]:
            hints = creativity_to_style_hints(creativity)
            assert "insider" in hints.lower()
            assert "opinion" in hints.lower()

    def test_creativity_to_style_hints_high(self) -> None:
        """High creativity gets thought leader style hints."""
        for creativity in [8, 9, 10]:
            hints = creativity_to_style_hints(creativity)
            assert "thought leader" in hints.lower()
            assert "contrarian" in hints.lower() or "provocative" in hints.lower()


class TestLengthMapping:
    """Tests for length to character range mapping."""

    def test_length_short(self) -> None:
        """Short length maps to 100-180 chars."""
        min_chars, max_chars = length_to_char_range("short")
        assert min_chars == 100
        assert max_chars == 180

    def test_length_medium(self) -> None:
        """Medium length maps to 180-280 chars."""
        min_chars, max_chars = length_to_char_range("medium")
        assert min_chars == 180
        assert max_chars == 280

    def test_length_long(self) -> None:
        """Long length maps to 280-400 chars."""
        min_chars, max_chars = length_to_char_range("long")
        assert min_chars == 280
        assert max_chars == 400

    def test_length_default(self) -> None:
        """Unknown length defaults to medium."""
        min_chars, max_chars = length_to_char_range("unknown")
        assert min_chars == 180
        assert max_chars == 280


class TestPromptGeneration:
    """Tests for tweet generation prompt."""

    def test_prompt_includes_creativity_level(self) -> None:
        """Prompt includes the creativity level."""
        system_msg, _ = get_tweet_generation_prompt(creativity=7)
        assert "7" in system_msg
        assert "/10" in system_msg

    def test_prompt_includes_style_hints(self) -> None:
        """Prompt includes appropriate style hints for creativity level."""
        system_msg, _ = get_tweet_generation_prompt(creativity=9)
        assert "thought leader" in system_msg.lower()

    def test_prompt_has_json_format(self) -> None:
        """Prompt requests JSON output format."""
        system_msg, _ = get_tweet_generation_prompt(creativity=5)
        assert "json" in system_msg.lower()
        assert "suggestions" in system_msg

    def test_user_template_has_placeholders(self) -> None:
        """User template has required placeholders."""
        _, user_template = get_tweet_generation_prompt(creativity=5)
        assert "{title}" in user_template
        assert "{url}" in user_template
        assert "{summary}" in user_template

    def test_user_message_included(self) -> None:
        """User guidance is included in template."""
        _, user_template = get_tweet_generation_prompt(
            creativity=5, user_message="focus on startups"
        )
        assert "focus on startups" in user_template

    def test_prompt_includes_length_short(self) -> None:
        """Prompt includes correct char limits for short length."""
        system_msg, _ = get_tweet_generation_prompt(creativity=5, length="short")
        assert "100-180" in system_msg
        assert "180 max" in system_msg

    def test_prompt_includes_length_medium(self) -> None:
        """Prompt includes correct char limits for medium length."""
        system_msg, _ = get_tweet_generation_prompt(creativity=5, length="medium")
        assert "180-280" in system_msg
        assert "280 max" in system_msg

    def test_prompt_includes_length_long(self) -> None:
        """Prompt includes correct char limits for long length."""
        system_msg, _ = get_tweet_generation_prompt(creativity=5, length="long")
        assert "280-400" in system_msg
        assert "400 max" in system_msg


class TestContentContextExtraction:
    """Tests for extracting content context for tweet generation."""

    def test_extract_article_context(self) -> None:
        """Extract context from article content."""
        from unittest.mock import MagicMock

        # Mock ContentData to avoid strict Pydantic validation
        content = MagicMock()
        content.id = 1
        content.content_type = ContentType.ARTICLE
        content.url = "https://example.com/article"
        content.display_title = "Great Article Title"
        content.source = "Tech Blog"
        content.platform = "substack"
        content.short_summary = None
        content.summary = None
        content.metadata = {
            "source": "Tech Blog",
            "platform": "substack",
            "final_url_after_redirects": "https://example.com/final-article",
            "summary": {
                "title": "Great Article Title",
                "overview": "This is the overview text.",
                "bullet_points": [
                    {"text": "First key point"},
                    {"text": "Second key point"},
                ],
            },
        }

        context = _extract_content_context(content)

        assert context["title"] == "Great Article Title"
        assert context["source"] == "Tech Blog"
        assert context["platform"] == "substack"
        assert context["url"] == "https://example.com/final-article"
        assert "overview" in context["summary"].lower()
        assert "First key point" in context["key_points"]

    def test_extract_news_context(self) -> None:
        """Extract context from news content."""
        from unittest.mock import MagicMock

        content = MagicMock()
        content.id = 2
        content.content_type = ContentType.NEWS
        content.url = "https://news.ycombinator.com/item?id=123"
        content.display_title = "News Title"
        content.source = "Hacker News"
        content.platform = "hackernews"
        content.short_summary = None
        content.summary = None
        content.metadata = {
            "source": "Hacker News",
            "platform": "hackernews",
            "article": {
                "url": "https://example.com/the-article",
                "title": "The Real Article",
            },
            "summary": {
                "title": "News Title",
                "article_url": "https://example.com/the-article",
                "overview": "News overview",
                "bullet_points": ["Point 1", "Point 2"],
            },
        }

        context = _extract_content_context(content)

        assert context["title"] == "News Title"
        assert "the-article" in context["url"]

    def test_extract_context_fallbacks(self) -> None:
        """Context extraction uses fallbacks for missing data."""
        from unittest.mock import MagicMock

        content = MagicMock()
        content.id = 3
        content.content_type = ContentType.ARTICLE
        content.url = "https://example.com/article"
        content.display_title = "Basic Title"
        content.source = None  # No source
        content.platform = None  # No platform
        content.short_summary = None
        content.summary = None
        content.metadata = {}

        context = _extract_content_context(content)

        assert context["title"] == "Basic Title"
        assert context["source"] == "Unknown"
        assert context["platform"] == "web"
        assert context["url"] == "https://example.com/article"
        # New fields should return N/A when missing
        assert context["quotes"] == "N/A"
        assert context["questions"] == "N/A"
        assert context["counter_arguments"] == "N/A"

    def test_extract_context_with_quotes_questions_counterargs(self) -> None:
        """Context extraction includes quotes, questions, and counter-arguments."""
        from unittest.mock import MagicMock

        content = MagicMock()
        content.id = 4
        content.content_type = ContentType.ARTICLE
        content.url = "https://example.com/article"
        content.display_title = "Article With Full Summary"
        content.source = "Tech Blog"
        content.platform = "substack"
        content.short_summary = None
        content.summary = None
        content.metadata = {
            "summary": {
                "title": "Article With Full Summary",
                "overview": "This is a comprehensive overview.",
                "bullet_points": [{"text": "Key insight one"}],
                "quotes": [
                    {"text": "This is a notable quote from the article."},
                    {"text": "Another important quote."},
                ],
                "questions": [
                    "What are the implications for the industry?",
                    "How might this affect consumers?",
                ],
                "counter_arguments": [
                    "Critics argue this approach has limitations.",
                    "Some experts suggest alternative solutions.",
                ],
            },
        }

        context = _extract_content_context(content)

        # Verify quotes are extracted
        assert "notable quote" in context["quotes"]
        assert "important quote" in context["quotes"]

        # Verify questions are extracted
        assert "implications for the industry" in context["questions"]
        assert "affect consumers" in context["questions"]

        # Verify counter-arguments are extracted
        assert "limitations" in context["counter_arguments"]
        assert "alternative solutions" in context["counter_arguments"]


class TestResponseParsing:
    """Tests for parsing LLM responses."""

    def test_parse_valid_json(self) -> None:
        """Parse valid JSON response."""
        response = json.dumps(
            {
                "suggestions": [
                    {"id": 1, "text": "Tweet 1", "style_label": "insightful"},
                    {"id": 2, "text": "Tweet 2", "style_label": "provocative"},
                    {"id": 3, "text": "Tweet 3", "style_label": "reflective"},
                ]
            }
        )

        result = _parse_suggestions_response(response)

        assert result is not None
        assert len(result) == 3
        assert result[0]["text"] == "Tweet 1"

    def test_parse_json_in_markdown_fence(self) -> None:
        """Parse JSON wrapped in markdown code fences."""
        response = """```json
{
  "suggestions": [
    {"id": 1, "text": "Tweet 1", "style_label": "a"},
    {"id": 2, "text": "Tweet 2", "style_label": "b"},
    {"id": 3, "text": "Tweet 3", "style_label": "c"}
  ]
}
```"""

        result = _parse_suggestions_response(response)

        assert result is not None
        assert len(result) == 3

    def test_parse_json_in_plain_fence(self) -> None:
        """Parse JSON wrapped in plain code fences."""
        response = """```
{
  "suggestions": [
    {"id": 1, "text": "Tweet 1", "style_label": "a"},
    {"id": 2, "text": "Tweet 2", "style_label": "b"},
    {"id": 3, "text": "Tweet 3", "style_label": "c"}
  ]
}
```"""

        result = _parse_suggestions_response(response)

        assert result is not None
        assert len(result) == 3

    def test_parse_invalid_json(self) -> None:
        """Invalid JSON returns None."""
        response = "This is not valid JSON at all"

        result = _parse_suggestions_response(response)

        assert result is None

    def test_parse_wrong_count(self) -> None:
        """Wrong number of suggestions returns None."""
        response = json.dumps(
            {
                "suggestions": [
                    {"id": 1, "text": "Only one tweet", "style_label": "a"},
                ]
            }
        )

        result = _parse_suggestions_response(response)

        assert result is None


class TestTweetValidation:
    """Tests for tweet validation and truncation."""

    def test_validate_normal_tweets(self) -> None:
        """Tweets under 400 chars pass through unchanged."""
        suggestions = [
            {"id": 1, "text": "Short tweet", "style_label": "a"},
            {"id": 2, "text": "Another tweet", "style_label": "b"},
            {"id": 3, "text": "Third tweet", "style_label": "c"},
        ]

        result = _validate_and_truncate_tweets(suggestions)

        assert len(result) == 3
        assert result[0].text == "Short tweet"

    def test_truncate_long_tweet(self) -> None:
        """Tweets over 400 chars are truncated with ellipsis."""
        long_text = "A" * 450  # Over 400 chars
        suggestions = [
            {"id": 1, "text": long_text, "style_label": "a"},
            {"id": 2, "text": "Normal tweet", "style_label": "b"},
            {"id": 3, "text": "Another normal", "style_label": "c"},
        ]

        result = _validate_and_truncate_tweets(suggestions)

        assert len(result[0].text) == 400
        assert result[0].text.endswith("...")

    def test_truncate_with_custom_max_chars(self) -> None:
        """Tweets are truncated based on custom max_chars."""
        text_200 = "A" * 200  # Over 180 chars for short
        suggestions = [
            {"id": 1, "text": text_200, "style_label": "a"},
            {"id": 2, "text": "Normal", "style_label": "b"},
            {"id": 3, "text": "Another", "style_label": "c"},
        ]

        # Test with short limit (180)
        result = _validate_and_truncate_tweets(suggestions, max_chars=180)
        assert len(result[0].text) == 180
        assert result[0].text.endswith("...")

        # Test with medium limit (280) - should not truncate
        result = _validate_and_truncate_tweets(suggestions, max_chars=280)
        assert len(result[0].text) == 200
        assert not result[0].text.endswith("...")

    def test_preserve_style_labels(self) -> None:
        """Style labels are preserved in validation."""
        suggestions = [
            {"id": 1, "text": "Tweet 1", "style_label": "insightful"},
            {"id": 2, "text": "Tweet 2", "style_label": None},
            {"id": 3, "text": "Tweet 3", "style_label": "bold"},
        ]

        result = _validate_and_truncate_tweets(suggestions)

        assert result[0].style_label == "insightful"
        assert result[1].style_label is None
        assert result[2].style_label == "bold"


class TestTweetSuggestionService:
    """Integration tests for the TweetSuggestionService."""

    @patch("app.services.tweet_suggestions.Agent.run_sync")
    def test_generate_suggestions_success(self, mock_run_sync) -> None:
        """Successfully generate tweet suggestions."""
        from app.services.tweet_suggestions import TweetSuggestionService

        mock_payload = TweetSuggestionsPayload(
            suggestions=[
                TweetSuggestionLLM(id=1, text="Great article!", style_label="a"),
                TweetSuggestionLLM(id=2, text="Must read this", style_label="b"),
                TweetSuggestionLLM(id=3, text="Interesting take", style_label="c"),
            ]
        )
        mock_result = MagicMock()
        mock_result.output = mock_payload
        mock_result.usage.return_value = MagicMock(input_tokens=100, output_tokens=50)
        mock_run_sync.return_value = mock_result

        # Use MagicMock for content to avoid strict Pydantic validation
        content = MagicMock()
        content.id = 1
        content.content_type = ContentType.ARTICLE
        content.url = "https://example.com/article"
        content.display_title = "Test Article"
        content.source = "Tech Blog"
        content.platform = "substack"
        content.short_summary = None
        content.summary = None
        content.metadata = {
            "source": "Tech Blog",
            "summary": {
                "title": "Article Title",
                "overview": "This is the overview text.",
                "bullet_points": [{"text": "Key point"}],
            },
        }

        original_key = settings.google_api_key
        settings.google_api_key = "test-key"
        service = TweetSuggestionService()
        try:
            result = service.generate_suggestions(content, creativity=5, length="short")
        finally:
            settings.google_api_key = original_key

        assert result is not None
        assert result.content_id == 1
        assert result.creativity == 5
        assert result.length == "short"
        assert result.model == TWEET_MODEL
        assert len(result.suggestions) == 3
        assert result.suggestions[0].text == "Great article!"

    @patch("app.services.tweet_suggestions.Agent.run_sync")
    def test_generate_suggestions_podcast_supported(self, mock_run_sync) -> None:
        """Podcasts are supported for tweet suggestions."""
        from app.services.tweet_suggestions import TweetSuggestionService

        original_key = settings.google_api_key
        settings.google_api_key = "test-key"
        mock_payload = TweetSuggestionsPayload(
            suggestions=[
                TweetSuggestionLLM(id=1, text="Podcast insight 1", style_label="a"),
                TweetSuggestionLLM(id=2, text="Podcast insight 2", style_label="b"),
                TweetSuggestionLLM(id=3, text="Podcast insight 3", style_label="c"),
            ]
        )
        mock_result = MagicMock()
        mock_result.output = mock_payload
        mock_result.usage.return_value = None
        mock_run_sync.return_value = mock_result

        content = ContentData(
            id=1,
            content_type=ContentType.PODCAST,
            url="https://example.com/podcast",
            title="Test Podcast",
            status=ContentStatus.COMPLETED,
            metadata={
                "summary": {
                    "title": "Podcast Episode",
                    "overview": "Overview of the podcast.",
                    "bullet_points": ["Key takeaway"],
                }
            },
        )

        service = TweetSuggestionService()
        try:
            result = service.generate_suggestions(content, creativity=5)
        finally:
            settings.google_api_key = original_key

        assert result is not None
        assert len(result.suggestions) == 3


class TestTweetModelSelection:
    """Tests for tweet model resolution."""

    def test_default_model_used(self) -> None:
        """Default model spec is returned when provider is not set."""
        service = TweetSuggestionService()
        assert service._get_model_for_provider(None) == TWEET_MODEL

    def test_provider_specific_model_used(self) -> None:
        """Provider override uses the mapped model spec when available."""
        service = TweetSuggestionService()
        for provider, model_spec in TWEET_MODELS.items():
            assert service._get_model_for_provider(provider) == model_spec
