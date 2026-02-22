from app.constants import (
    SUMMARY_KIND_LONG_BULLETS,
    SUMMARY_KIND_LONG_EDITORIAL_NARRATIVE,
    SUMMARY_KIND_LONG_INTERLEAVED,
    SUMMARY_KIND_LONG_STRUCTURED,
    SUMMARY_KIND_SHORT_NEWS_DIGEST,
    SUMMARY_VERSION_V1,
    SUMMARY_VERSION_V2,
)
from app.utils.summary_metadata import infer_summary_kind_version


def test_infer_summary_kind_version_interleaved_v1() -> None:
    summary = {"summary_type": "interleaved", "insights": [{"topic": "AI"}]}
    result = infer_summary_kind_version("article", summary, None, None)
    assert result == (SUMMARY_KIND_LONG_INTERLEAVED, SUMMARY_VERSION_V1)


def test_infer_summary_kind_version_news_digest() -> None:
    summary = {"summary_type": "news_digest", "summary": "Quick summary"}
    result = infer_summary_kind_version("article", summary, None, None)
    assert result == (SUMMARY_KIND_SHORT_NEWS_DIGEST, SUMMARY_VERSION_V1)


def test_infer_summary_kind_version_interleaved_v2() -> None:
    summary = {"key_points": [{"text": "Point"}], "topics": [{"topic": "AI"}]}
    result = infer_summary_kind_version("podcast", summary, None, None)
    assert result == (SUMMARY_KIND_LONG_INTERLEAVED, SUMMARY_VERSION_V2)


def test_infer_summary_kind_version_structured() -> None:
    summary = {"overview": "Overview", "bullet_points": [{"text": "Point"}]}
    result = infer_summary_kind_version("article", summary, None, None)
    assert result == (SUMMARY_KIND_LONG_STRUCTURED, SUMMARY_VERSION_V1)


def test_infer_summary_kind_version_bullets() -> None:
    summary = {"points": [{"text": "Point"}]}
    result = infer_summary_kind_version("article", summary, None, None)
    assert result == (SUMMARY_KIND_LONG_BULLETS, SUMMARY_VERSION_V1)


def test_infer_summary_kind_version_editorial_narrative() -> None:
    summary = {
        "editorial_narrative": "Narrative paragraph with enough substance.",
        "key_points": [{"point": "A concrete point"}],
    }
    result = infer_summary_kind_version("article", summary, None, None)
    assert result == (SUMMARY_KIND_LONG_EDITORIAL_NARRATIVE, SUMMARY_VERSION_V1)


def test_infer_summary_kind_version_news_content_type_defaults() -> None:
    summary = {"key_points": ["Item"], "summary": "Digest"}
    result = infer_summary_kind_version("news", summary, None, None)
    assert result == (SUMMARY_KIND_SHORT_NEWS_DIGEST, SUMMARY_VERSION_V1)


def test_infer_summary_kind_version_preserves_kind_for_missing_version() -> None:
    summary = {"key_points": [{"text": "Point"}], "topics": [{"topic": "AI"}]}
    result = infer_summary_kind_version(
        "article",
        summary,
        SUMMARY_KIND_LONG_INTERLEAVED,
        None,
    )
    assert result == (SUMMARY_KIND_LONG_INTERLEAVED, SUMMARY_VERSION_V2)
