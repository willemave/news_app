from app.models.contracts import ContentType
from app.utils.summarization_inputs import build_summarization_payload


def test_news_payload_includes_embedded_video_transcript() -> None:
    payload = build_summarization_payload(
        ContentType.NEWS,
        {
            "content_to_summarize": "Tweet text",
            "video_transcript": "Speaker explains the demo.",
            "article": {"url": "https://x.com/i/status/123", "title": "Tweet text"},
        },
    )

    assert "Tweet text" in payload
    assert "[Embedded video transcript]\nSpeaker explains the demo." in payload


def test_article_payload_includes_embedded_video_transcript() -> None:
    payload = build_summarization_payload(
        ContentType.ARTICLE,
        {
            "content_to_summarize": "Tweet text",
            "video_transcript": "Speaker explains the demo.",
        },
    )

    assert "Tweet text" in payload
    assert "[Embedded video transcript]\nSpeaker explains the demo." in payload
