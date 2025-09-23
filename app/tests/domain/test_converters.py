from app.domain.converters import content_to_domain, normalize_news_metadata
from app.models.metadata import ContentStatus, ContentType
from app.models.schema import Content


def _build_news_content(metadata: dict) -> Content:
    content = Content(
        id=101,
        content_type=ContentType.NEWS.value,
        url="https://example.com/story",
        title="Example Story",
        status=ContentStatus.NEW.value,
        content_metadata=metadata,
    )
    content.platform = "reddit"
    content.source = "r/news"
    return content


def test_content_to_domain_populates_article_for_legacy_news_payload() -> None:
    metadata = {
        "platform": "reddit",
        "source": "r/news",
        "items": [
            {
                "title": "Example Story",
                "url": "https://example.com/story",
                "source": "example.com",
            }
        ],
    }

    content = _build_news_content(metadata)
    domain_content = content_to_domain(content)

    assert domain_content.metadata["article"]["url"] == "https://example.com/story"
    assert domain_content.metadata["article"]["title"] == "Example Story"
    assert domain_content.metadata["article"]["source_domain"] == "example.com"


def test_normalize_news_metadata_uses_fallback_values() -> None:
    metadata = {"platform": "reddit", "source": "example.com"}

    normalized = normalize_news_metadata(
        metadata,
        fallback_url="https://example.com/story",
        fallback_title="Example Story",
        fallback_source="example.com",
    )

    assert normalized["article"]["url"] == "https://example.com/story"
    assert normalized["article"]["title"] == "Example Story"
    assert normalized["article"]["source_domain"] == "example.com"
