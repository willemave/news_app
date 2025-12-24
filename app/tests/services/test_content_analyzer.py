"""Tests for content analyzer service."""

from unittest.mock import patch

import pytest

from app.models.metadata import ContentType
from app.services.content_analyzer import (
    AnalysisError,
    ContentAnalysisResult,
    ContentAnalyzer,
    get_content_analyzer,
)
from app.services.content_submission import (
    infer_content_type_and_platform,
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


class TestInferContentTypeAndPlatform:
    """Tests for infer_content_type_and_platform function."""

    def test_explicit_type_returned(self):
        """Explicit content type should be returned as-is."""
        content_type, platform = infer_content_type_and_platform(
            "https://unknown-site.com/something",
            provided_type=ContentType.ARTICLE,
            platform_hint="custom",
        )
        assert content_type == ContentType.ARTICLE
        assert platform == "custom"

    def test_spotify_detected_as_podcast(self):
        """Spotify URLs should be detected as podcast."""
        content_type, platform = infer_content_type_and_platform(
            "https://open.spotify.com/episode/abc123",
            provided_type=None,
            platform_hint=None,
        )
        assert content_type == ContentType.PODCAST
        assert platform == "spotify"

    def test_path_keyword_detection(self):
        """URLs with podcast keywords in path should be detected as podcast."""
        content_type, platform = infer_content_type_and_platform(
            "https://unknown-site.com/podcast/episode/123",
            provided_type=None,
            platform_hint=None,
        )
        assert content_type == ContentType.PODCAST

    def test_unknown_url_defaults_to_article(self):
        """Unknown URLs without podcast keywords should default to article."""
        content_type, platform = infer_content_type_and_platform(
            "https://example.com/some-page",
            provided_type=None,
            platform_hint=None,
        )
        assert content_type == ContentType.ARTICLE


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
    """Tests for ContentAnalyzer class using pydantic-ai."""

    @patch("app.services.content_analyzer.get_settings")
    def test_missing_api_key_raises_error(self, mock_settings):
        """Missing API key should raise ValueError."""
        mock_settings.return_value.openai_api_key = None
        analyzer = ContentAnalyzer()

        with pytest.raises(ValueError, match="OPENAI_API_KEY not configured"):
            analyzer._get_agent()

    @patch("app.services.content_analyzer._fetch_page_content")
    @patch("app.services.content_analyzer.get_settings")
    def test_analyze_url_with_spotify_link(self, mock_settings, mock_fetch):
        """URL with Spotify link is detected as podcast."""
        mock_settings.return_value.openai_api_key = "test-key"

        # Mock page fetch with Spotify link in HTML
        mock_fetch.return_value = (
            '<a href="https://open.spotify.com/episode/abc123">Listen</a>',
            "Test Episode Title\nSome content...",
        )

        analyzer = ContentAnalyzer()
        result = analyzer.analyze_url("https://example.com/pod")

        assert isinstance(result, ContentAnalysisResult)
        assert result.content_type == "podcast"
        assert "spotify.com" in result.media_url
        assert result.platform == "spotify"
        assert result.confidence >= 0.8  # LLM returns variable confidence

    @patch("app.services.content_analyzer._fetch_page_content")
    @patch("app.services.content_analyzer.get_settings")
    def test_analyze_url_fetch_failure_returns_error(self, mock_settings, mock_fetch):
        """Failed page fetch returns AnalysisError."""
        mock_settings.return_value.openai_api_key = "test-key"
        mock_fetch.return_value = (None, None)

        analyzer = ContentAnalyzer()
        result = analyzer.analyze_url("https://example.com/article")

        assert isinstance(result, AnalysisError)
        assert result.recoverable is True


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
