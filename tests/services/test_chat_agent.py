from app.models.metadata import ContentType
from app.models.schema import Content
from app.services.chat_agent import build_article_context


def test_build_article_context_includes_full_transcript_with_budget() -> None:
    transcript = "a" * 5000
    content = Content(content_type=ContentType.PODCAST.value, url="https://example.com")
    content.content_metadata = {"transcript": transcript}

    context = build_article_context(content, include_full_text=True, max_tokens=5000)

    assert context is not None
    assert transcript in context


def test_build_article_context_prefers_summary_over_full_text_when_requested() -> None:
    content_text = "b" * 5000
    content = Content(content_type=ContentType.ARTICLE.value, url="https://example.com")
    content.content_metadata = {
        "content": content_text,
        "summary": {
            "overview": "Overview text",
            "bullet_points": [
                {"text": "Point one", "category": "key_finding"},
                {"text": "Point two", "category": "methodology"},
                {"text": "Point three", "category": "conclusion"},
            ],
            "quotes": [{"text": "Quote text", "context": "Author"}],
            "topics": ["AI", "Productivity"],
            "questions": ["What changes next?"],
            "counter_arguments": ["Skeptics argue this is premature."],
            "classification": "to_read",
        },
        "summary_kind": "long_structured",
        "summary_version": 1,
    }

    context = build_article_context(content, include_full_text=False, max_tokens=5000)

    assert context is not None
    assert "Overview text" in context
    assert "Point one" in context
    assert "Quote text" in context
    assert "Skeptics argue this is premature." in context
    assert content_text not in context


def test_build_article_context_falls_back_to_summary_when_budget_exceeded() -> None:
    content_text = "c" * 5000
    content = Content(content_type=ContentType.ARTICLE.value, url="https://example.com")
    content.content_metadata = {
        "content": content_text,
        "summary": {
            "overview": "Short overview",
            "bullet_points": [
                {"text": "Point one", "category": "key_finding"},
                {"text": "Point two", "category": "methodology"},
                {"text": "Point three", "category": "conclusion"},
            ],
            "quotes": [],
            "topics": ["AI"],
        },
        "summary_kind": "long_structured",
        "summary_version": 1,
    }

    context = build_article_context(content, include_full_text=True, max_tokens=50)

    assert context is not None
    assert "Short overview" in context
    assert content_text not in context
