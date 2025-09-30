import logging
from pathlib import Path

import pytest

from app.scraping.podcast_unified import PodcastUnifiedScraper
from app.scraping.substack_unified import load_substack_feeds
from app.scraping.reddit_unified import RedditUnifiedScraper
from app.utils.error_logger import get_scraper_metrics, reset_scraper_metrics


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    reset_scraper_metrics()


def test_substack_missing_config_logs_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    monkeypatch.setenv("NEWSAPP_CONFIG_DIR", str(config_dir))
    caplog.set_level(logging.WARNING)

    feeds = load_substack_feeds()
    assert feeds == []

    # Second call should not emit a duplicate warning
    feeds = load_substack_feeds()
    assert feeds == []

    warn_messages = [record.message for record in caplog.records if record.levelno == logging.WARNING]
    missing_logs = [message for message in warn_messages if "config_missing" in message]
    assert len(missing_logs) == 1

    metrics = get_scraper_metrics()
    assert metrics["Substack"]["scrape_config_missing"] == 1


def test_substack_env_override_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg = config_dir / "substack.yml"
    cfg.write_text(
        """feeds:\n  - name: Test\n    url: https://example.com/feed\n    limit: 3\n""",
        encoding="utf-8",
    )

    monkeypatch.setenv("NEWSAPP_CONFIG_DIR", str(config_dir))

    feeds = load_substack_feeds()
    assert feeds == [
        {
            "url": "https://example.com/feed",
            "name": "Test",
            "limit": 3,
        }
    ]

    metrics = get_scraper_metrics()
    assert "Substack" not in metrics or "scrape_config_missing" not in metrics["Substack"]


def test_podcast_missing_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    monkeypatch.setenv("NEWSAPP_CONFIG_DIR", str(config_dir))
    caplog.set_level(logging.WARNING)

    scraper = PodcastUnifiedScraper()
    assert scraper.feeds == []

    warn_messages = [record.message for record in caplog.records if record.levelno == logging.WARNING]
    assert any("config_missing" in message for message in warn_messages)

    metrics = get_scraper_metrics()
    assert metrics["Podcast"]["scrape_config_missing"] == 1


def test_reddit_config_env_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    cfg = config_dir / "reddit.yml"
    cfg.write_text(
        """subreddits:\n  - name: MachineLearning\n    limit: 5\n""",
        encoding="utf-8",
    )

    monkeypatch.setenv("NEWSAPP_CONFIG_DIR", str(config_dir))

    scraper = RedditUnifiedScraper()
    assert scraper.subreddits == {"MachineLearning": 5}

    metrics = get_scraper_metrics()
    assert "Reddit" not in metrics or "scrape_config_missing" not in metrics["Reddit"]
