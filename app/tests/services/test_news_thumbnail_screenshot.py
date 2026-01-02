"""Tests for news thumbnail screenshot service."""


from app.services import news_thumbnail_screenshot as nts


def test_select_normalized_url_prefers_article_url() -> None:
    content = nts.NewsContentSnapshot(
        content_type="news",
        url="https://fallback.example.com",
        metadata={
            "article": {"url": "https://article.example.com"},
            "summary": {"final_url_after_redirects": "https://final.example.com"},
        },
    )

    assert nts._select_normalized_url(content) == "https://article.example.com"


def test_generate_placeholder_writes_file(tmp_path, monkeypatch) -> None:
    placeholder_path = tmp_path / "placeholder.png"
    placeholder_path.write_bytes(b"placeholder")

    news_dir = tmp_path / "news_thumbnails"
    monkeypatch.setattr(nts, "PLACEHOLDER_PATH", placeholder_path)
    monkeypatch.setattr(nts, "PLACEHOLDER_DIR", placeholder_path.parent)
    monkeypatch.setattr(nts, "get_news_thumbnails_dir", lambda: news_dir)
    monkeypatch.setattr(nts, "_generate_thumbnail", lambda source_path, content_id: None)

    result = nts._generate_placeholder(42, "fallback")

    assert result.success is True
    assert (news_dir / "42.png").exists()


def test_generate_news_thumbnail_uses_placeholder_on_failure(monkeypatch) -> None:
    content = nts.NewsContentSnapshot(
        content_type="news",
        url="https://fallback.example.com",
        metadata={
            "article": {"url": "https://article.example.com"},
            "content": "News content",
        },
    )

    monkeypatch.setattr(nts, "_load_news_snapshot", lambda content_id: content)
    monkeypatch.setattr(
        nts,
        "_capture_screenshot",
        lambda request: nts.NewsThumbnailResult(
            content_id=request.content_id,
            success=False,
            error_message="boom",
        ),
    )
    monkeypatch.setattr(
        nts,
        "_generate_placeholder",
        lambda content_id, reason: nts.NewsThumbnailResult(
            content_id=content_id,
            success=True,
            image_path="/tmp/placeholder.png",
            thumbnail_path=None,
        ),
    )

    result = nts.generate_news_thumbnail(nts.NewsThumbnailJob(content_id=1))

    assert result.success is True
    assert result.used_placeholder is True
