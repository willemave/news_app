import pytest
import yt_dlp

from app.processing_strategies.youtube_strategy import YouTubeProcessorStrategy


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error_message",
    [
        "Sign in to confirm you're not a bot",
        "Premieres in 5 minutes",
    ],
)
async def test_youtube_strategy_skips_known_download_errors(mocker, error_message):
    class DummyYDL:
        def __init__(self, _opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _url, download=False):
            raise yt_dlp.utils.DownloadError(error_message)

    mocker.patch(
        "app.processing_strategies.youtube_strategy.yt_dlp.YoutubeDL",
        DummyYDL,
    )

    strategy = YouTubeProcessorStrategy(http_client=mocker.Mock())
    result = await strategy.extract_data(b"", "https://youtube.com/watch?v=abc")

    assert result["skip_processing"] is True
    assert "skip_reason" in result


@pytest.mark.asyncio
async def test_youtube_strategy_sets_text_content(mocker):
    class DummyYDL:
        def __init__(self, _opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _url, download=False):
            return {
                "id": "abc123",
                "title": "Sample Video",
                "uploader": "Test Channel",
                "description": "Video description",
                "duration": 120,
                "upload_date": "20250101",
                "view_count": 1000,
                "like_count": 50,
                "thumbnail": "https://example.com/thumb.jpg",
            }

    mocker.patch(
        "app.processing_strategies.youtube_strategy.yt_dlp.YoutubeDL",
        DummyYDL,
    )
    mocker.patch(
        "app.processing_strategies.youtube_strategy.YouTubeProcessorStrategy._extract_transcript",
        return_value=None,
    )

    strategy = YouTubeProcessorStrategy(http_client=mocker.Mock())
    result = await strategy.extract_data(b"", "https://youtube.com/watch?v=abc")

    assert result["text_content"]
    assert result["content_type"] == "text"
