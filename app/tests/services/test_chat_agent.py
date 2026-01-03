from app.models.metadata import ContentType
from app.models.schema import Content
from app.services.chat_agent import build_article_context


def test_build_article_context_includes_full_transcript_on_first_message() -> None:
    transcript = "a" * 5000
    content = Content(content_type=ContentType.PODCAST.value, url="https://example.com")
    content.content_metadata = {"transcript": transcript}

    context = build_article_context(content, include_full_text=True)

    assert context is not None
    assert transcript in context


def test_build_article_context_truncates_transcript_by_default() -> None:
    transcript = "b" * 5000
    content = Content(content_type=ContentType.PODCAST.value, url="https://example.com")
    content.content_metadata = {"transcript": transcript}

    context = build_article_context(content, include_full_text=False)

    assert context is not None
    assert transcript not in context
    assert transcript[:4000] + "..." in context


def test_build_article_context_includes_full_content_on_first_message() -> None:
    content_text = "c" * 5000
    content = Content(content_type=ContentType.ARTICLE.value, url="https://example.com")
    content.content_metadata = {"content": content_text}

    context = build_article_context(content, include_full_text=True)

    assert context is not None
    assert content_text in context
