from app.constants import SUMMARY_KIND_SHORT_NEWS_DIGEST, SUMMARY_VERSION_V1
from app.domain.converters import content_to_domain
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


def test_content_to_domain_preserves_article_metadata() -> None:
    metadata = {
        "platform": "reddit",
        "source": "r/news",
        "article": {
            "title": "Example Story",
            "url": "https://example.com/story",
            "source_domain": "example.com",
        },
    }

    content = _build_news_content(metadata)
    domain_content = content_to_domain(content)

    assert domain_content.metadata["article"]["url"] == "https://example.com/story"
    assert domain_content.metadata["article"]["title"] == "Example Story"
    assert domain_content.metadata["article"]["source_domain"] == "example.com"


def test_content_to_domain_sets_news_summary_kind() -> None:
    metadata = {
        "summary": {
            "title": "Digest title",
            "summary": "Short digest summary",
            "classification": "to_read",
        }
    }

    content = _build_news_content(metadata)
    domain_content = content_to_domain(content)

    assert domain_content.metadata["summary_kind"] == SUMMARY_KIND_SHORT_NEWS_DIGEST
    assert domain_content.metadata["summary_version"] == SUMMARY_VERSION_V1
