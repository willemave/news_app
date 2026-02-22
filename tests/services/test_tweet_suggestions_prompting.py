"""Tests for tweet prompt and mapping helpers."""

import pytest

from app.services.llm_prompts import (
    creativity_to_style_hints,
    get_tweet_generation_prompt,
    length_to_char_range,
)
from app.services.tweet_suggestions import creativity_to_temperature


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
        assert creativity_to_temperature(0) == pytest.approx(0.1)
        assert creativity_to_temperature(15) == pytest.approx(1.0)

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
            creativity=5,
            user_message="focus on startups",
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
