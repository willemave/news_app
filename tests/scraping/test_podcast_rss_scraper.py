from contextlib import contextmanager
from unittest.mock import Mock, patch

import pytest

from app.models.metadata import ContentStatus, ContentType
from app.scraping.podcast_unified import PodcastUnifiedScraper


def _build_item(url: str, user_id: int | None = None) -> dict:
    return {
        "url": url,
        "title": "Test Episode",
        "content_type": ContentType.PODCAST,
        "metadata": {"source": "Test Podcast", "platform": "podcast"},
        "user_id": user_id,
    }


@pytest.mark.parametrize(
    "status",
    [
        ContentStatus.NEW.value,
        "downloaded",
        "transcribed",
        "summarized",
        ContentStatus.FAILED.value,
    ],
)
def test_existing_podcast_entries_are_skipped(status):
    """Ensure duplicate podcast items do not create new records regardless of status."""
    existing = Mock()
    existing.id = 123
    existing.status = status

    mock_db = Mock()
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    @contextmanager
    def _db_context():
        yield mock_db

    with (
        patch("app.scraping.base.get_db", lambda: _db_context()),
        patch("app.scraping.base.get_queue_service", return_value=Mock()),
        patch("app.scraping.base.ensure_inbox_status", return_value=False),
    ):
        scraper = PodcastUnifiedScraper()
        stats = scraper._save_items_with_stats([_build_item("https://example.com/ep1")])

    assert stats["duplicates"] == 1
    mock_db.add.assert_not_called()
