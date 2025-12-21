"""Tests for content analyzer service."""

from unittest.mock import MagicMock, patch

import pytest

from app.models.metadata import ContentType
from app.services.content_analyzer import (
    AnalysisError,
    ContentAnalysisResult,
    ContentAnalyzer,
    get_content_analyzer,
)
from app.services.content_submission import (
    analyze_and_classify_url,
    should_use_llm_analysis,
)


class TestShouldUseLLMAnalysis:
    """Tests for should_use_llm_analysis function."""

    def test_skips_spotify(self):
        """Known Spotify URLs should skip LLM analysis."""
        assert not should_use_llm_analysis("https://open.spotify.com/episode/abc123")
        assert not should_use_llm_analysis("https://spotify.link/xyz")

    def test_skips_youtube(self):
        """Known YouTube URLs should skip LLM analysis."""
        assert not should_use_llm_analysis("https://youtube.com/watch?v=abc123")
        assert not should_use_llm_analysis("https://www.youtube.com/watch?v=abc123")
        assert not should_use_llm_analysis("https://youtu.be/abc123")
        assert not should_use_llm_analysis("https://m.youtube.com/watch?v=abc123")

    def test_skips_apple_podcasts(self):
        """Known Apple Podcast URLs should skip LLM analysis."""
        assert not should_use_llm_analysis("https://podcasts.apple.com/us/podcast/xyz")
        assert not should_use_llm_analysis("https://music.apple.com/us/album/xyz")

    def test_skips_overcast(self):
        """Known Overcast URLs should skip LLM analysis."""
        assert not should_use_llm_analysis("https://overcast.fm/+abc123")

    def test_uses_llm_for_unknown_urls(self):
        """Unknown URLs should use LLM analysis."""
        assert should_use_llm_analysis("https://example.com/some-podcast")
        assert should_use_llm_analysis("https://transistor.fm/episode/123")
        assert should_use_llm_analysis("https://medium.com/article")
        assert should_use_llm_analysis("https://substack.com/post/title")


class TestContentAnalysisResult:
    """Tests for ContentAnalysisResult Pydantic model."""

    def test_article_result(self):
        """Test creating an article analysis result."""
        result = ContentAnalysisResult(
            content_type="article",
            original_url="https://example.com/article",
            title="Test Article",
            platform="medium",
        )
        assert result.content_type == "article"
        assert result.media_url is None
        assert result.confidence == 0.8  # default

    def test_podcast_result_with_media_url(self):
        """Test creating a podcast result with media URL."""
        result = ContentAnalysisResult(
            content_type="podcast",
            original_url="https://example.com/podcast/episode",
            media_url="https://cdn.example.com/audio.mp3",
            media_format="mp3",
            title="Test Podcast Episode",
            duration_seconds=3600,
            platform="transistor",
            confidence=0.95,
        )
        assert result.content_type == "podcast"
        assert result.media_url == "https://cdn.example.com/audio.mp3"
        assert result.media_format == "mp3"
        assert result.duration_seconds == 3600

    def test_video_result(self):
        """Test creating a video analysis result."""
        result = ContentAnalysisResult(
            content_type="video",
            original_url="https://vimeo.com/123456",
            media_url="https://player.vimeo.com/video/123456.mp4",
            media_format="mp4",
            platform="vimeo",
        )
        assert result.content_type == "video"
        assert result.media_format == "mp4"


class TestContentAnalyzer:
    """Tests for ContentAnalyzer class."""

    @patch("app.services.content_analyzer.get_settings")
    def test_missing_api_key_raises_error(self, mock_settings):
        """Missing API key should raise ValueError."""
        mock_settings.return_value.openai_api_key = None
        analyzer = ContentAnalyzer()

        with pytest.raises(ValueError, match="OPENAI_API_KEY not configured"):
            analyzer._get_client()

    @patch("app.services.content_analyzer.OpenAI")
    @patch("app.services.content_analyzer.get_settings")
    def test_analyze_url_success(self, mock_settings, mock_openai):
        """Successful URL analysis returns ContentAnalysisResult."""
        mock_settings.return_value.openai_api_key = "test-key"

        # Mock the response
        mock_response = MagicMock()
        mock_response.output_text = (
            '{"content_type": "podcast", "original_url": "https://example.com/pod", '
            '"media_url": "https://cdn.example.com/audio.mp3", "media_format": "mp3", '
            '"title": "Test Episode", "description": null, "duration_seconds": 1800, '
            '"platform": "transistor", "confidence": 0.9}'
        )

        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_response
        mock_openai.return_value = mock_client

        analyzer = ContentAnalyzer()
        result = analyzer.analyze_url("https://example.com/pod")

        assert isinstance(result, ContentAnalysisResult)
        assert result.content_type == "podcast"
        assert result.media_url == "https://cdn.example.com/audio.mp3"
        assert result.platform == "transistor"

    @patch("app.services.content_analyzer.OpenAI")
    @patch("app.services.content_analyzer.get_settings")
    def test_analyze_url_no_output(self, mock_settings, mock_openai):
        """No output from OpenAI returns AnalysisError."""
        mock_settings.return_value.openai_api_key = "test-key"

        mock_response = MagicMock()
        mock_response.output_text = None
        mock_response.output = None

        mock_client = MagicMock()
        mock_client.responses.create.return_value = mock_response
        mock_openai.return_value = mock_client

        analyzer = ContentAnalyzer()
        result = analyzer.analyze_url("https://example.com/article")

        assert isinstance(result, AnalysisError)
        assert "No output" in result.message

    @patch("app.services.content_analyzer.OpenAI")
    @patch("app.services.content_analyzer.get_settings")
    def test_analyze_url_api_error(self, mock_settings, mock_openai):
        """API errors return AnalysisError with recoverable flag."""
        from openai import RateLimitError

        mock_settings.return_value.openai_api_key = "test-key"

        mock_client = MagicMock()
        mock_client.responses.create.side_effect = RateLimitError(
            message="Rate limit exceeded",
            response=MagicMock(status_code=429),
            body=None,
        )
        mock_openai.return_value = mock_client

        analyzer = ContentAnalyzer()
        result = analyzer.analyze_url("https://example.com/article")

        assert isinstance(result, AnalysisError)
        assert result.recoverable is True


class TestAnalyzeAndClassifyUrl:
    """Tests for analyze_and_classify_url integration."""

    def test_explicit_type_skips_analysis(self):
        """Explicit content type should skip LLM analysis entirely."""
        content_type, platform, extra_metadata = analyze_and_classify_url(
            "https://unknown-site.com/something",
            provided_type=ContentType.ARTICLE,
            platform_hint="custom",
        )

        assert content_type == ContentType.ARTICLE
        assert platform == "custom"
        assert extra_metadata == {}

    def test_known_platform_uses_pattern_detection(self):
        """Known platforms should use pattern detection, not LLM."""
        content_type, platform, extra_metadata = analyze_and_classify_url(
            "https://open.spotify.com/episode/abc123",
            provided_type=None,
            platform_hint=None,
        )

        assert content_type == ContentType.PODCAST
        assert platform == "spotify"
        assert extra_metadata == {}

    def test_youtube_uses_pattern_detection(self):
        """YouTube should use pattern detection."""
        content_type, platform, extra_metadata = analyze_and_classify_url(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            provided_type=None,
            platform_hint=None,
        )

        # YouTube is detected as article by pattern matching (no podcast keywords)
        # but this is expected behavior for the pattern matcher
        assert content_type in [ContentType.ARTICLE, ContentType.PODCAST]

    @patch("app.services.content_submission.get_content_analyzer")
    def test_unknown_url_uses_llm_analysis(self, mock_get_analyzer):
        """Unknown URLs should trigger LLM analysis."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_url.return_value = ContentAnalysisResult(
            content_type="podcast",
            original_url="https://transistor.fm/episode/123",
            media_url="https://media.transistor.fm/audio.mp3",
            media_format="mp3",
            title="Great Episode",
            platform="transistor",
        )
        mock_get_analyzer.return_value = mock_analyzer

        content_type, platform, extra_metadata = analyze_and_classify_url(
            "https://transistor.fm/episode/123",
            provided_type=None,
            platform_hint=None,
        )

        assert content_type == ContentType.PODCAST
        assert platform == "transistor"
        assert extra_metadata["audio_url"] == "https://media.transistor.fm/audio.mp3"
        assert extra_metadata["extracted_title"] == "Great Episode"

    @patch("app.services.content_submission.get_content_analyzer")
    def test_llm_analysis_failure_falls_back(self, mock_get_analyzer):
        """LLM analysis failure should fall back to pattern detection."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_url.return_value = AnalysisError(
            message="API timeout", recoverable=True
        )
        mock_get_analyzer.return_value = mock_analyzer

        content_type, platform, extra_metadata = analyze_and_classify_url(
            "https://unknown-site.com/podcast/episode",
            provided_type=None,
            platform_hint=None,
        )

        # Falls back to pattern detection which finds "podcast" in path
        assert content_type == ContentType.PODCAST
        assert extra_metadata == {}  # No LLM-extracted metadata

    @patch("app.services.content_submission.get_content_analyzer")
    def test_video_mapped_to_podcast(self, mock_get_analyzer):
        """Video content type should be mapped to podcast for processing."""
        mock_analyzer = MagicMock()
        mock_analyzer.analyze_url.return_value = ContentAnalysisResult(
            content_type="video",
            original_url="https://vimeo.com/123456",
            media_url="https://player.vimeo.com/video/123456.mp4",
            media_format="mp4",
            platform="vimeo",
        )
        mock_get_analyzer.return_value = mock_analyzer

        content_type, platform, extra_metadata = analyze_and_classify_url(
            "https://vimeo.com/123456",
            provided_type=None,
            platform_hint=None,
        )

        assert content_type == ContentType.PODCAST  # Video mapped to podcast
        assert extra_metadata["is_video"] is True
        assert extra_metadata["video_url"] == "https://vimeo.com/123456"


class TestGetContentAnalyzer:
    """Tests for get_content_analyzer singleton."""

    def test_returns_singleton(self):
        """get_content_analyzer should return the same instance."""
        # Reset the global instance
        import app.services.content_analyzer as ca_module

        ca_module._content_analyzer = None

        analyzer1 = get_content_analyzer()
        analyzer2 = get_content_analyzer()

        assert analyzer1 is analyzer2
